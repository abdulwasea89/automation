import os
import re
import json
import requests
from typing import Dict, List
from src.config import settings
from src.logger import get_logger
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import asyncio

logger = get_logger("zoko_client")
ZOKO_API_URL = settings.ZOKO_API_URL

class ZokoClient:
    """Enhanced Zoko WhatsApp client with connection pooling and error handling."""

    def __init__(self):
        self.api_url = "https://chat.zoko.io/v2/message"
        self.api_key = settings.ZOKO_API_KEY
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "apikey": self.api_key
        }
        
        # Create session with connection pooling
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=4,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        # Configure adapter with connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.available_templates = self._load_available_templates()

    def _load_available_templates(self) -> Dict[str, Dict]:
        """Load available templates from zoko_templates.json for validation."""
        try:
            template_file = os.path.join(os.path.dirname(__file__), '..', './zoko_templates.json')
            if os.path.exists(template_file):
                with open(template_file, 'r') as f:
                    templates = json.load(f)
                    return {t['templateId']: t for t in templates if t.get('active', True)}
            logger.warning("zoko_templates.json not found, template validation disabled")
            return {}
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
            return {}

    def _validate_phone(self, chat_id: str) -> str:
        """Validate and format phone number."""
        match = re.match(r"^\+?[1-9]\d{9,14}$", chat_id)
        if not match:
            raise ValueError(f"Invalid WhatsApp number format: {chat_id}")
        return chat_id.lstrip("+")

    async def send_text(self, chat_id: str, text: str) -> bool:
        """Send plain text message with connection pooling."""
        try:
            recipient = self._validate_phone(chat_id)
            payload = {
                "channel": "whatsapp",
                "recipient": recipient,
                "type": "text",
                "message": text
            }
            logger.info(f"Sending text message to {recipient}: {text[:50]}...")
            response = await asyncio.to_thread(lambda: self.session.post(self.api_url, json=payload, headers=self.headers, timeout=30))
            if response.status_code == 200:
                logger.info(f"Text message sent successfully to {recipient}")
                return True
            logger.error(f"Failed to send text message. Status: {response.status_code}, Response: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending text message to {chat_id}: {str(e)}", exc_info=True)
            return False

    async def send_button_template(self, chat_id: str, template_id: str, template_args: List[str]) -> bool:
        """Send WhatsApp button template message with connection pooling (async)."""
        try:
            recipient = self._validate_phone(chat_id)
            payload = {
                "channel": "whatsapp",
                "recipient": recipient,
                "type": "buttonTemplate",
                "templateId": template_id,
                "templateArgs": template_args
            }
            logger.info(f"Sending button template {template_id} to {recipient}")
            response = await asyncio.to_thread(
                lambda: self.session.post(self.api_url, json=payload, headers=self.headers, timeout=30)
            )
            logger.info(f"Zoko API response: status={response.status_code}, body={response.text}")
            if response.status_code == 200:
                logger.info(f"Button template sent successfully to {recipient}")
                return True
            logger.error(f"Failed to send button template. Status: {response.status_code}, Response: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending button template to {chat_id}: {str(e)}", exc_info=True)
            return False

    async def send_interactive_list(self, chat_id: str, header: str, body: str, items: List[Dict], section_title: str = None, footer: str = None) -> bool:
        """Send WhatsApp interactive list message with optimized endpoint selection (async)."""
        endpoints = [
            "https://chat.zoko.io/v2/message",  # Primary endpoint
            "https://chat.api.zoko.io/v2/message"  # Fallback endpoint
        ]
        try:
            recipient = self._validate_phone(chat_id)
            section_title = section_title or header or "LEVA Houses"
            list_title = str(header)[:24] if header else "LEVA Houses"
            section_title = str(section_title)[:24]
            # Validate and sanitize items
            valid_items = []
            seen_payloads = set()
            def clean_text(text, maxlen):
                # Remove emojis and non-ASCII
                text = re.sub(r'[^ -~]+', '', str(text))
                text = re.sub(r'<[^>]+>', '', text)
                text = re.sub(r'\s+', ' ', text)
                return text.strip()[:maxlen]
            for item in items:
                payload_val = str(item.get("payload", ""))[:200]
                title_val = clean_text(item.get("title", ""), 24)
                desc_val = clean_text(item.get("description", ""), 72)
                if not desc_val:
                    desc_val = "No description available"
                if not payload_val or not title_val or payload_val in seen_payloads:
                    logger.error(f"Invalid or duplicate interactive list item: {item}")
                    continue
                seen_payloads.add(payload_val)
                valid_items.append({
                    "id": payload_val,
                    "title": title_val,
                    "description": desc_val,
                    "payload": payload_val
                })
            if not valid_items:
                logger.error("No valid items for interactive list. Aborting send.")
                return False
            # Build sections (support multiple sections in the future)
            sections = [
                {
                    "title": section_title,
                    "items": valid_items
                }
            ]
            payload = {
                "channel": "whatsapp",
                "recipient": recipient,
                "type": "interactive_list",
                "interactiveList": {
                    "header": {"text": list_title},
                    "body": {"text": str(body)[:72]},
                    "footer": {"text": footer or "Powered by Zoko"},
                    "list": {
                        "title": list_title,
                        "sections": sections
                    }
                }
            }
            logger.info(f"Interactive list payload: {json.dumps(payload, ensure_ascii=False)}")
            # Try endpoints with connection pooling
            for endpoint in endpoints:
                logger.info(f"Trying to send interactive list to {recipient} using endpoint: {endpoint}")
                try:
                    response = await asyncio.to_thread(
                        lambda: self.session.post(endpoint, json=payload, headers=self.headers, timeout=30)
                    )
                    if response.status_code == 200:
                        logger.info(f"Interactive list sent successfully to {recipient} via {endpoint}")
                        return True
                    logger.warning(f"Endpoint {endpoint} failed with status {response.status_code}")
                except Exception as e:
                    logger.error(f"Exception sending to endpoint {endpoint}: {e}")
            logger.error(f"Failed to send interactive list to {recipient} using all endpoints.")
            return False
        except Exception as e:
            logger.error(f"Error sending interactive list to {chat_id}: {str(e)}", exc_info=True)
            return False

# Instantiate globally
zoko_client = ZokoClient() 