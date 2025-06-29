import os
import re
import json
import requests
from typing import Dict, List, Optional, Any
from src.config import settings
from src.logger import get_logger

logger = get_logger("zoko_client")

ZOKO_API_URL = settings.ZOKO_API_URL

class ZokoClient:
    """Enhanced Zoko WhatsApp client with rich template support and error handling."""
    
    def __init__(self):
        self.api_url = "https://chat.zoko.io/v2/message"  # Updated to correct endpoint
        self.api_key = settings.ZOKO_API_KEY
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json"
        }
        if self.api_key:
            self.headers["apikey"] = self.api_key  # Add API key to headers
        
        # Load available templates for validation
        self.available_templates = self._load_available_templates()
    
    def _load_available_templates(self) -> Dict[str, Dict]:
        """Load available templates from zoko_templates.json for validation."""
        try:
            template_file = os.path.join(os.path.dirname(__file__), '..', './zoko_templates.json')
            if os.path.exists(template_file):
                with open(template_file, 'r') as f:
                    templates = json.load(f)
                    return {t['templateId']: t for t in templates if t.get('active', True)}
            else:
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
    
    def _validate_template(self, template_id: str, template_type: str = "buttonTemplate") -> bool:
        """Validate if template exists and is active."""
        if not self.available_templates:
            return True  # Skip validation if templates not loaded
        
        template = self.available_templates.get(template_id)
        if not template:
            logger.warning(f"Template {template_id} not found in available templates")
            return False
        
        if template.get('templateType') != template_type:
            logger.warning(f"Template {template_id} is {template.get('templateType')}, not {template_type}")
            return False
        
        return template.get('active', True)
    
    def _validate_no_json_payload(self, data: Any, context: str, recipient: str) -> bool:
        """
        Comprehensive validation to ensure no JSON payloads are sent to users.
        
        Args:
            data: Data to validate
            context: Context for logging (e.g., "text message", "template args")
            recipient: Recipient phone number for logging
        
        Returns:
            True if safe, False if JSON payload detected
        """
        try:
            # Check if data is a dict (JSON object)
            if isinstance(data, dict):
                logger.critical(f"🚨 CRITICAL: {context} contains dict for {recipient}!")
                logger.critical(f"🚨 This would send JSON to user - BLOCKING!")
                logger.critical(f"🚨 Dict content: {data}")
                return False
            
            # Check if data is a list containing dicts
            if isinstance(data, list):
                for i, item in enumerate(data):
                    if isinstance(item, dict):
                        logger.critical(f"🚨 CRITICAL: {context} item {i} is dict for {recipient}!")
                        logger.critical(f"🚨 This would send JSON to user - BLOCKING!")
                        logger.critical(f"🚨 Item content: {item}")
                        return False
                    elif isinstance(item, str) and item.strip().startswith('{') and item.strip().endswith('}'):
                        try:
                            json.loads(item)
                            logger.critical(f"🚨 CRITICAL: {context} item {i} is JSON string for {recipient}!")
                            logger.critical(f"🚨 JSON content: {item}")
                            return False
                        except json.JSONDecodeError:
                            pass  # Not valid JSON, safe to use
            
            # Check if data is a JSON string
            elif isinstance(data, str) and data.strip().startswith('{') and data.strip().endswith('}'):
                try:
                    json.loads(data)
                    logger.critical(f"🚨 CRITICAL: {context} is JSON string for {recipient}!")
                    logger.critical(f"🚨 JSON content: {data}")
                    return False
                except json.JSONDecodeError:
                    pass  # Not valid JSON, safe to use
            
            return True
            
        except Exception as e:
            logger.error(f"Error in JSON validation for {context}: {e}")
            return False  # Fail safe - block if validation fails
    
    def _is_new_customer_error(self, response_text: str) -> bool:
        """Check if error is due to new customer restriction."""
        return "New customer - please use template message" in response_text
    
    def _get_fallback_template(self, template_type: str = "buttonTemplate") -> Optional[str]:
        """Get a fallback template for the given type."""
        fallback_templates = {
            "buttonTemplate": "welcome___product_finder_flow",
            "richTemplate": "zoko_upsell_product_01"
        }
        return fallback_templates.get(template_type)
    
    def send_text(self, chat_id: str, text: str) -> bool:
        """Send plain text message with fallback to template for new customers."""
        try:
            recipient = self._validate_phone(chat_id)
            
            # CRITICAL: Comprehensive JSON validation for text content
            if not self._validate_no_json_payload(text, "text message", recipient):
                logger.critical(f"🚨 CRITICAL: JSON payload detected in text message for {recipient} - BLOCKING!")
                return False
            
            # Use correct payload format as per Zoko API documentation
            payload = {
                "channel": "whatsapp",
                "recipient": recipient,
                "type": "text",
                "message": text
            }
            
            logger.info(f"Sending text message to {recipient}: {text[:50]}...")
            logger.info(f"Payload: {payload}")
            
            # Increase timeout to 30 seconds to prevent timeouts
            response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"Text message sent successfully to {recipient}")
                logger.info(f"Response: {response.text}")
                return True
            elif response.status_code == 409 and self._is_new_customer_error(response.text):
                logger.warning(f"New customer {recipient} - falling back to welcome template")
                # Fallback to welcome template for new customers
                return self.send_button_template(
                    chat_id, 
                    "welcome___product_finder_flow",
                    ["find_project_payload", "view_budget_payload", "contact_support_payload"]
                )
            else:
                logger.error(f"Failed to send text message. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending text message to {chat_id}: {str(e)}", exc_info=True)
            return False
    
    def send_button_template(self, chat_id: str, template_id: str, template_args: List[str]) -> bool:
        """
        Send WhatsApp button template message with validation and fallback.
        
        Args:
            chat_id: Recipient phone number
            template_id: Zoko template ID
            template_args: List of template arguments
        """
        try:
            recipient = self._validate_phone(chat_id)
            
            # CRITICAL: Comprehensive JSON validation for template arguments
            if not self._validate_no_json_payload(template_args, "template arguments", recipient):
                logger.critical(f"🚨 CRITICAL: JSON payload detected in template args for {recipient} - BLOCKING!")
                return False
            
            # Validate template before sending
            if not self._validate_template(template_id, "buttonTemplate"):
                fallback_template = self._get_fallback_template("buttonTemplate")
                if fallback_template and fallback_template != template_id:
                    logger.warning(f"Template {template_id} not found, using fallback {fallback_template}")
                    template_id = fallback_template
                    template_args = ["find_project_payload", "view_budget_payload", "contact_support_payload"]
                else:
                    logger.error(f"No valid fallback template available for {template_id}")
                    return False
            
            # Use correct payload format as per Zoko API documentation
            payload = {
                "channel": "whatsapp",
                "recipient": recipient,
                "type": "buttonTemplate",
                "templateId": template_id,
                "templateArgs": template_args
            }
            
            logger.info(f"Sending button template {template_id} to {recipient}")
            logger.info(f"Payload: {payload}")
            
            # Increase timeout to 30 seconds to prevent timeouts
            response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                logger.info(f"Button template sent successfully to {recipient}")
                logger.info(f"Response: {response.text}")
                return True
            else:
                logger.error(f"Failed to send button template. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending button template to {chat_id}: {str(e)}", exc_info=True)
            return False
    
    def send_rich_template(self, chat_id: str, template_id: str, template_args: List[str]) -> bool:
        """
        Send WhatsApp rich template message with image header.
        
        Args:
            chat_id: Recipient phone number
            template_id: Zoko template ID
            template_args: List of template arguments
        """
        try:
            recipient = self._validate_phone(chat_id)
            
            # CRITICAL: Comprehensive JSON validation for template arguments
            if not self._validate_no_json_payload(template_args, "template arguments", recipient):
                logger.critical(f"🚨 CRITICAL: JSON payload detected in template args for {recipient} - BLOCKING!")
                return False
            
            # Validate template before sending
            if not self._validate_template(template_id, "buttonTemplate"):  # Rich templates are buttonTemplate type
                fallback_template = self._get_fallback_template("richTemplate")
                if fallback_template and fallback_template != template_id:
                    logger.warning(f"Template {template_id} not found, using fallback {fallback_template}")
                    template_id = fallback_template
                    template_args = [
                        "https://via.placeholder.com/400x200?text=Property+Image",
                        "Luxury Property",
                        "PROP-001",
                        "buy_now_payload"
                    ]
                else:
                    logger.error(f"No valid fallback template available for {template_id}")
                    return False
            
            payload = {
                "channel": "whatsapp",
                "recipient": recipient,
                "type": "richTemplate",
                "templateId": template_id,
                "templateArgs": template_args
            }
            
            logger.info(f"Sending rich template {template_id} to {recipient}")
            response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Rich template sent successfully to {recipient}")
                return True
            else:
                logger.error(f"Failed to send rich template. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending rich template to {chat_id}: {str(e)}", exc_info=True)
            return False
    
    def send_interactive_list(self, chat_id: str, header: str, body: str, items: List[Dict]) -> bool:
        """
        Send WhatsApp interactive list message with proper title lengths and fallback.
        
        Args:
            chat_id: Recipient phone number
            header: List header text
            body: List body text
            items: List of items with title, description, and payload
        """
        try:
            recipient = self._validate_phone(chat_id)
            
            # Format items for Zoko API - ensure titles are under 24 characters
            formatted_items = []
            for item in items[:10]:  # Zoko limit
                title = item.get("title", "Item")
                # Truncate title if too long
                if len(title) > 24:
                    title = title[:21] + "..."
                
                formatted_items.append({
                    "title": title,
                    "description": item.get("description", ""),
                    "payload": item.get("payload", "default")
                })
            
            payload = {
                "channel": "whatsapp",
                "recipient": recipient,
                "type": "interactive_list",
                "interactiveList": {
                    "header": {"text": header},
                    "body": {"text": body},
                    "footer": {"text": "Powered by Property Assistant"},
                    "list": {
                        "title": "Properties",
                        "sections": [
                            {
                                "title": "Available Properties",
                                "items": formatted_items
                            }
                        ]
                    }
                }
            }
            
            logger.info(f"Sending interactive list to {recipient} with {len(formatted_items)} items")
            response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Interactive list sent successfully to {recipient}")
                return True
            elif response.status_code == 409 and self._is_new_customer_error(response.text):
                logger.warning(f"New customer {recipient} - falling back to welcome template")
                # Fallback to welcome template for new customers
                return self.send_button_template(
                    chat_id, 
                    "welcome___product_finder_flow",
                    ["find_project_payload", "view_budget_payload", "contact_support_payload"]
                )
            else:
                logger.error(f"Failed to send interactive list. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending interactive list to {chat_id}: {str(e)}", exc_info=True)
            return False

    def send_interactive_button(self, chat_id: str, header: str, body: str, buttons: List[Dict]) -> bool:
        """
        Send WhatsApp interactive button message with fallback.
        
        Args:
            chat_id: Recipient phone number
            header: Button header text
            body: Button body text
            buttons: List of button objects with title and payload
        """
        try:
            recipient = self._validate_phone(chat_id)
            
            payload = {
                "channel": "whatsapp",
                "recipient": recipient,
                "type": "interactive_button",
                "interactiveButton": {
                    "header": {"text": header},
                    "body": {"text": body},
                    "footer": {"text": "Powered by Property Assistant"},
                    "buttons": buttons
                }
            }
            
            logger.info(f"Sending interactive button to {recipient}")
            response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                logger.info(f"Interactive button sent successfully to {recipient}")
                return True
            elif response.status_code == 409 and self._is_new_customer_error(response.text):
                logger.warning(f"New customer {recipient} - falling back to welcome template")
                # Fallback to welcome template for new customers
                return self.send_button_template(
                    chat_id, 
                    "welcome___product_finder_flow",
                    ["find_project_payload", "view_budget_payload", "contact_support_payload"]
                )
            else:
                logger.error(f"Failed to send interactive button. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending interactive button to {chat_id}: {str(e)}", exc_info=True)
            return False

    def send_rich_message(self, chat_id: str, message_data: Dict) -> bool:
        """
        Send rich WhatsApp message based on message data structure with enhanced error handling.
        
        Args:
            chat_id: Recipient phone number
            message_data: Dictionary containing message type and payload
        """
        try:
            whatsapp_type = message_data.get("whatsapp_type", "text")
            
            if whatsapp_type == "buttonTemplate":
                template = message_data.get("template", {})
                return self.send_button_template(
                    chat_id,
                    template.get("template_id", ""),
                    template.get("template_args", [])
                )
            
            elif whatsapp_type == "richTemplate":
                template = message_data.get("template", {})
                return self.send_rich_template(
                    chat_id,
                    template.get("template_id", ""),
                    template.get("template_args", [])
                )
            
            elif whatsapp_type == "interactive_list":
                template = message_data.get("template", {})
                args = template.get("template_args", [])
                if len(args) >= 3:
                    items = json.loads(args[2]) if isinstance(args[2], str) else args[2]
                    return self.send_interactive_list(chat_id, args[0], args[1], items)
                else:
                    logger.error("Invalid interactive list template args")
                    return False
            
            elif whatsapp_type == "interactive_button":
                template = message_data.get("template", {})
                args = template.get("template_args", [])
                if len(args) >= 3:
                    buttons = json.loads(args[2]) if isinstance(args[2], str) else args[2]
                    return self.send_interactive_button(chat_id, args[0], args[1], buttons)
                else:
                    logger.error("Invalid interactive button template args")
                    return False
            
            else:
                # Fallback to text message
                message = message_data.get("message", "No message content")
                return self.send_text(chat_id, message)
                
        except Exception as e:
            logger.error(f"Error sending rich message to {chat_id}: {str(e)}", exc_info=True)
            return False

    def get_available_templates(self) -> Dict[str, Dict]:
        """Get list of available templates."""
        return self.available_templates.copy()

    def validate_template(self, template_id: str, template_type: str = "buttonTemplate") -> bool:
        """Public method to validate template existence."""
        return self._validate_template(template_id, template_type)

# Global client instance
zoko_client = ZokoClient()

# Backward compatibility functions
def send_text(chat_id: str, text: str) -> bool:
    """Send plain text message (backward compatibility)."""
    return zoko_client.send_text(chat_id, text)

def send_whatsapp_message(chat_id: str, whatsapp_type: str, whatsapp_payload: dict) -> bool:
    """Send WhatsApp message (backward compatibility)."""
    if whatsapp_type == "buttonTemplate":
        return zoko_client.send_button_template(
            chat_id,
            whatsapp_payload.get("templateId", ""),
            whatsapp_payload.get("templateArgs", [])
        )
    elif whatsapp_type == "interactive_list":
        return zoko_client.send_interactive_list(
            chat_id,
            whatsapp_payload.get("header", "Properties"),
            whatsapp_payload.get("body", "Available properties"),
            whatsapp_payload.get("items", [])
        )
    elif whatsapp_type == "interactive_button":
        return zoko_client.send_interactive_button(
            chat_id,
            whatsapp_payload.get("header", "Options"),
            whatsapp_payload.get("body", "Please choose an option"),
            whatsapp_payload.get("buttons", [])
        )
    else:
        return zoko_client.send_text(chat_id, str(whatsapp_payload))

def send_template(chat_id: str, template_id: str, template_args: list) -> bool:
    """Send template message (backward compatibility)."""
    return zoko_client.send_button_template(chat_id, template_id, template_args)