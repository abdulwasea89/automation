"""
Zoko WhatsApp Utilities
Helper functions for template management, debugging, and customer status.
"""

import os
import json
import requests
from typing import Dict, List, Optional, Any
from src.config import settings
from src.logger import get_logger
import re

logger = get_logger("zoko_utils")

class ZokoUtils:
    """Utility class for Zoko WhatsApp operations."""
    
    def __init__(self):
        self.api_url = settings.ZOKO_API_URL
        self.api_key = settings.ZOKO_API_KEY
        self.headers = {
            "accept": "application/json",
            "content-type": "application/json"
        }
        if self.api_key:
            self.headers["apikey"] = self.api_key
    
    def get_templates(self) -> List[Dict]:
        """Fetch available templates from Zoko API."""
        try:
            # Note: This endpoint might not exist in Zoko API, using local file as fallback
            template_file = os.path.join(os.path.dirname(__file__), '..','./zoko_templates.json')
            if os.path.exists(template_file):
                with open(template_file, 'r') as f:
                    return json.load(f)
            else:
                logger.warning("zoko_templates.json not found")
                return []
        except Exception as e:
            logger.error(f"Failed to load templates: {e}")
            return []
    
    def validate_template(self, template_id: str, template_type: str = "buttonTemplate") -> Dict:
        """Validate template and return details."""
        templates = self.get_templates()
        
        for template in templates:
            if template.get('templateId') == template_id:
                if template.get('templateType') == template_type:
                    return {
                        'valid': True,
                        'template': template,
                        'active': template.get('active', True)
                    }
                else:
                    return {
                        'valid': False,
                        'error': f"Template type mismatch. Expected {template_type}, got {template.get('templateType')}",
                        'template': template
                    }
        
        return {
            'valid': False,
            'error': f"Template {template_id} not found",
            'template': None
        }
    
    def get_template_suggestions(self, template_type: str = "buttonTemplate") -> List[Dict]:
        """Get suggestions for templates of a specific type."""
        templates = self.get_templates()
        suggestions = []
        
        for template in templates:
            if template.get('templateType') == template_type and template.get('active', True):
                suggestions.append({
                    'templateId': template.get('templateId'),
                    'description': template.get('templateDesc', 'No description'),
                    'variables': template.get('templateVariableCount', 0),
                    'language': template.get('templateLanguage', 'en')
                })
        
        return suggestions
    
    def check_customer_status(self, phone_number: str) -> Dict:
        """Check if a customer is new or existing (approximate)."""
        try:
            # Try to send a simple text message to check status
            payload = {
                "channel": "whatsapp",
                "recipient": phone_number.lstrip("+"),
                "type": "text",
                "message": "Status check"
            }
            
            response = requests.post(self.api_url, json=payload, headers=self.headers, timeout=10)
            
            if response.status_code == 409 and "New customer" in response.text:
                return {
                    'status': 'new_customer',
                    'message': 'Customer requires template messages for first contact',
                    'can_send_text': False,
                    'can_send_interactive': False,
                    'can_send_templates': True
                }
            elif response.status_code == 200:
                return {
                    'status': 'existing_customer',
                    'message': 'Customer can receive all message types',
                    'can_send_text': True,
                    'can_send_interactive': True,
                    'can_send_templates': True
                }
            else:
                return {
                    'status': 'unknown',
                    'message': f'Unknown status: {response.status_code}',
                    'can_send_text': False,
                    'can_send_interactive': False,
                    'can_send_templates': True  # Templates usually work
                }
                
        except Exception as e:
            logger.error(f"Failed to check customer status: {e}")
            return {
                'status': 'error',
                'message': f'Error checking status: {str(e)}',
                'can_send_text': False,
                'can_send_interactive': False,
                'can_send_templates': True
            }
    
    def get_message_recommendations(self, customer_status: str, message_type: str = "general") -> List[str]:
        """Get message type recommendations based on customer status."""
        recommendations = {
            'new_customer': {
                'general': [
                    "Use buttonTemplate messages for first contact",
                    "Welcome templates work well for new customers",
                    "Avoid text messages and interactive messages initially"
                ],
                'property_search': [
                    "Use welcome___product_finder_flow template",
                    "Provide clear call-to-action buttons",
                    "Include property search options"
                ],
                'support': [
                    "Use technical_support template for help",
                    "Provide structured support options",
                    "Include contact information"
                ]
            },
            'existing_customer': {
                'general': [
                    "All message types are available",
                    "Interactive messages work within 24h window",
                    "Text messages are allowed"
                ],
                'property_search': [
                    "Use interactive_list for multiple properties",
                    "Use buttonTemplate for single property details",
                    "Text messages for quick responses"
                ],
                'support': [
                    "Interactive buttons for support categories",
                    "Text messages for quick help",
                    "Template messages for structured support"
                ]
            }
        }
        
        return recommendations.get(customer_status, {}).get(message_type, ["Use template messages as fallback"])
    
    def format_template_args(self, template_id: str, args: List[str]) -> List[str]:
        """Format template arguments based on template requirements."""
        validation = self.validate_template(template_id)
        
        if not validation['valid']:
            logger.warning(f"Template {template_id} not found, using default args")
            return args
        
        template = validation['template']
        required_vars = template.get('templateVariableCount', 0)
        
        # Pad with default values if not enough args provided
        while len(args) < required_vars:
            args.append(f"default_arg_{len(args) + 1}")
        
        # Truncate if too many args provided
        if len(args) > required_vars:
            args = args[:required_vars]
            logger.warning(f"Too many args provided for {template_id}, truncated to {required_vars}")
        
        return args
    
    def create_welcome_message(self, customer_name: str = None) -> Dict:
        """Create a welcome message structure."""
        message = {
            "whatsapp_type": "buttonTemplate",
            "template": {
                "template_id": "welcome___product_finder_flow",
                "template_args": [
                    "find_project_payload",
                    "view_budget_payload", 
                    "contact_support_payload"
                ]
            }
        }
        
        if customer_name:
            # Could customize template args with customer name if template supports it
            logger.info(f"Welcome message prepared for {customer_name}")
        
        return message
    
    def create_product_list_message(self, products: List[Dict]) -> Dict:
        """Create an interactive list message for products using templates."""
        if not products:
            return {
                "whatsapp_type": "text",
                "message": "No products found matching your criteria. Please try a different search."
            }
        # Format products for interactive list
        items = []
        for prod in products[:10]:
            items.append({
                "title": prod.get('title', 'Product')[:24],
                "description": prod.get('description', '')[:72],
                "payload": f"product_{prod.get('id', 'unknown')}"
            })
        return {
            "whatsapp_type": "interactive_list",
            "template": {
                "template_args": [
                    "Available Products",
                    f"Found {len(products)} products matching your criteria:",
                    json.dumps(items)
                ]
            }
        }
    
    def create_product_detail_message(self, product_data: Dict) -> Dict:
        """Create a button template message for product details."""
        template_suggestions = self.get_template_suggestions("buttonTemplate")
        template = next((tpl for tpl in template_suggestions if tpl['variables'] == 4), template_suggestions[0])
        template_id = template['templateId']
        def clean_text(text, maxlen):
            text = re.sub(r'<[^>]+>', '', str(text))  # Remove HTML
            text = re.sub(r'[^\w\s\-\.,:;!?()&]', '', text)  # Remove special chars except basic punctuation
            return text.strip()[:maxlen]
        image_url = product_data.get("image_url", "https://via.placeholder.com/400x300?text=Product")
        title = clean_text(product_data.get("title", "Product"), 24)
        # For zoko_upsell_product_01, use [image_url, title, title, 'Buy Now']
        template_args = [image_url, title, title, "Buy Now"]
        return {
            "whatsapp_type": "buttonTemplate",
            "template": {
                "template_id": template_id,
                "template_args": template_args
            },
            "product_data": product_data
        }
    
    def debug_message_send(self, chat_id: str, message_data: Dict) -> Dict:
        """Debug a message send operation with detailed analysis."""
        debug_info = {
            'chat_id': chat_id,
            'message_type': message_data.get('whatsapp_type', 'unknown'),
            'customer_status': None,
            'template_validation': None,
            'recommendations': [],
            'potential_issues': []
        }
        
        # Check customer status
        customer_status = self.check_customer_status(chat_id)
        debug_info['customer_status'] = customer_status
        
        # Validate template if applicable
        if message_data.get('whatsapp_type') in ['buttonTemplate', 'richTemplate']:
            template_id = message_data.get('template', {}).get('template_id')
            if template_id:
                validation = self.validate_template(template_id, message_data.get('whatsapp_type'))
                debug_info['template_validation'] = validation
        
        # Generate recommendations
        if customer_status['status'] == 'new_customer':
            debug_info['recommendations'] = self.get_message_recommendations('new_customer', 'general')
            
            if message_data.get('whatsapp_type') in ['text', 'interactive_list', 'interactive_button']:
                debug_info['potential_issues'].append("New customers cannot receive this message type")
        
        # Check for common issues
        if message_data.get('whatsapp_type') == 'interactive_list':
            template_args = message_data.get('template', {}).get('template_args', [])
            if len(template_args) >= 3:
                try:
                    items = json.loads(template_args[2]) if isinstance(template_args[2], str) else template_args[2]
                    for item in items:
                        if len(item.get('title', '')) > 24:
                            debug_info['potential_issues'].append(f"Item title too long: {item.get('title')}")
                except:
                    debug_info['potential_issues'].append("Invalid JSON in interactive list items")
        
        return debug_info

# Global utility instance
zoko_utils = ZokoUtils()

# Convenience functions
def get_available_templates() -> List[Dict]:
    """Get all available templates."""
    return zoko_utils.get_templates()

def validate_template(template_id: str, template_type: str = "buttonTemplate") -> Dict:
    """Validate a template."""
    return zoko_utils.validate_template(template_id, template_type)

def check_customer_status(phone_number: str) -> Dict:
    """Check customer status."""
    return zoko_utils.check_customer_status(phone_number)

def debug_message(chat_id: str, message_data: Dict) -> Dict:
    """Debug a message before sending."""
    return zoko_utils.debug_message_send(chat_id, message_data)

def list_available_templates(template_type: str = "buttonTemplate", language: str = "en") -> list:
    """
    List available templates for the AI/chatbot to choose from.
    """
    templates = []
    try:
        with open(os.path.join(os.path.dirname(__file__), '..', './zoko_templates.json'), 'r') as f:
            all_templates = json.load(f)
            for t in all_templates:
                if t.get('templateType') == template_type and t.get('templateLanguage', 'en') == language and t.get('active', True):
                    templates.append({
                        'templateId': t['templateId'],
                        'desc': t.get('templateDesc', ''),
                        'variableCount': t.get('templateVariableCount', 0)
                    })
    except Exception as e:
        logger.error(f"Failed to list templates: {e}")
    return templates

def send_ai_chosen_template(chat_id: str, template_id: str, template_args: list, template_type: str = "buttonTemplate") -> bool:
    """
    Send a WhatsApp template message using ZokoClient, with template and args chosen by AI.
    - chat_id: recipient number (string)
    - template_id: templateId from zoko_templates.json
    - template_args: list of arguments (AI fills these)
    - template_type: buttonTemplate (default)
    """
    # Validate template and get variable count
    templates = list_available_templates(template_type)
    match = next((t for t in templates if t['templateId'] == template_id), None)
    if not match:
        logger.error(f"Template {template_id} not found or inactive.")
        return False
    # Use format_template_args to pad/truncate
    args = zoko_utils.format_template_args(template_id, template_args)
    from src.zoko_client import zoko_client
    logger.info(f"Sending template {template_id} to {chat_id} with args: {args}")
    return zoko_client.send_button_template(chat_id, template_id, args) 