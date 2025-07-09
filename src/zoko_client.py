import os
import re
import json
import requests
from typing import Dict, List
from src.config import settings
from src.logger import get_logger

logger = get_logger("zoko_client")
ZOKO_API_URL = settings.ZOKO_API_URL

class ZokoClient:
    """Enhanced Zoko WhatsApp client with rich template support and error handling."""

    def __init__(self):
        self.api_url = "https://chat.zoko.io/v2/message"
        self.api_key = settings.ZOKO_API_KEY
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "apikey": self.api_key
        }
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

    def send_text(self, chat_id: str, text: str) -> bool:
        """Send plain text message with fallback to template for new customers."""
        try:
            recipient = self._validate_phone(chat_id)
            payload = {
                "channel": "whatsapp",
                "recipient": recipient,
                "type": "text",
                "message": text
            }
            logger.info(f"Sending text message to {recipient}: {text[:50]}...")
            response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=30)
            if response.status_code == 200:
                logger.info(f"Text message sent successfully to {recipient}")
                return True
            logger.error(f"Failed to send text message. Status: {response.status_code}, Response: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending text message to {chat_id}: {str(e)}", exc_info=True)
            return False

    def send_button_template(self, chat_id: str, template_id: str, template_args: List[str]) -> bool:
        """Send WhatsApp button template message."""
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
            response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=30)
            if response.status_code == 200:
                logger.info(f"Button template sent successfully to {recipient}")
                return True
            logger.error(f"Failed to send button template. Status: {response.status_code}, Response: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending button template to {chat_id}: {str(e)}", exc_info=True)
            return False

    def send_interactive_list(self, chat_id: str, header: str, body: str, items: List[Dict]) -> bool:
        """Send WhatsApp interactive list message. Tries all Zoko endpoints if needed."""
        endpoints = [
            "https://chat.api.zoko.io/v2/account/templates",
            "https://chat.zoko.io/v2/account/templates",
            "https://chat.zoko.io/v2/message",
            "https://chat.api.zoko.io/v2/message"   
        ]
        try:
            recipient = self._validate_phone(chat_id)
            short_title = "LEVA Houses"

            if not items or not isinstance(items, list):
                logger.error("interactiveList.items is empty or not a list. Aborting send.")
                return False

            # Validate each item structure
            for item in items:
                if "id" not in item or "title" not in item:
                    logger.error(f"Invalid interactive list item format: {item}")
                    return False

            payload = {
                "channel": "whatsapp",
                "recipient": recipient,
                "type": "interactive_list",
                "interactiveList": {
                    "body": {"text": body},
                    "list": {
                        "title": short_title,
                        "header": {"text": short_title},
                        "sections": [
                            {
                                "title": short_title,
                                "items": items
                            }
                        ]
                    }
                }
            }

            for endpoint in endpoints:
                logger.info(f"Trying to send interactive list to {recipient} using endpoint: {endpoint}")
                try:
                    response = requests.post(endpoint, json=payload, headers=self.headers, timeout=30)
                    logger.info(f"Endpoint: {endpoint}, Status: {response.status_code}, Response: {response.text}")
                    if response.status_code == 200:
                        logger.info(f"Interactive list sent successfully to {recipient} via {endpoint}")
                        return True
                except Exception as e:
                    logger.error(f"Exception sending to endpoint {endpoint}: {e}")
            logger.error(f"Failed to send interactive list to {recipient} using all endpoints.")
            return False
        except Exception as e:
            logger.error(f"Error sending interactive list to {chat_id}: {str(e)}", exc_info=True)
            return False

# Instantiate globally
zoko_client = ZokoClient()
