"""
Product Showcase Module
Handles product display with images, names, and buy buttons/links in WhatsApp messages.
"""

import json
import os
from typing import Dict, List, Optional, Any
from src.zoko_client import ZokoClient
from src.zoko_utils import zoko_utils
from src.logger import get_logger
import re
from src.product_loader import product_loader

logger = get_logger("product_showcase")

class ProductShowcase:
    """Product showcase functionality for WhatsApp messages."""
    
    def __init__(self):
        self.client = ZokoClient()
        self.utils = zoko_utils
    
    def create_product_card(self, product: Dict) -> Dict:
        """
        Create a product card message with image, name, and buy button.
        
        Args:
            product: Dictionary containing product information
                - id: Product ID
                - name: Product name
                - image_url: Product image URL
                - price: Product price
                - description: Product description
                - buy_url: Direct buy link (optional)
                - buy_payload: Buy button payload (optional)
        """
        try:
            template_id = "zoko_upsell_product_01"
            image_url = product.get('image_url', 'https://via.placeholder.com/400x200?text=Product+Image')
            def clean_text(text, maxlen):
                text = re.sub(r'<[^>]+>', '', str(text))  # Remove HTML
                text = re.sub(r'[^\w\s\-\.,:;!?()&]', '', text)  # Remove special chars except basic punctuation
                return text.strip()[:maxlen]
            product_name = clean_text(product.get('name', 'Product'), 24)
            product_id = clean_text(product.get('id', 'PROD-001'), 32)
            buy_action = clean_text(product.get('buy_payload', f'buy_now_{product_id}'), 32)
            if product.get('buy_url'):
                buy_action = clean_text(f"buy_url_{product_id}", 32)
            template_args = [image_url, product_name, product_name, "Buy Now"]
            if template_id == "welcome___product_finder_flow":
                template_args = template_args[:3]
            return {
                "whatsapp_type": "buttonTemplate",
                "template": {
                    "template_id": template_id,
                    "template_args": template_args
                },
                "product_data": product
            }
        except Exception as e:
            logger.error(f"Failed to create product card: {e}")
            return self._create_fallback_product_message(product)
    
    def create_product_list(self, products: List[Dict]) -> Dict:
        """
        Create an interactive list of products.
        
        Args:
            products: List of product dictionaries
        """
        try:
            if not products:
                return {
                    "whatsapp_type": "text",
                    "message": "No products available at the moment. Please check back later!"
                }
            
            # Format products for interactive list
            items = []
            for product in products[:10]:  # Zoko limit
                # Build a concise, info-rich summary for WhatsApp/Zoko
                title = product.get('name', 'Product')[:24]  # 24 char limit
                type_ = product.get('type', '')
                cat = product.get('category', '')
                vendor = product.get('vendor', '')
                price = product.get('price', 'N/A')
                desc = product.get('description', '')
                # Remove HTML tags from desc
                import re
                desc = re.sub('<[^<]+?>', '', desc)
                # Compose a short summary (type/category, vendor, price, short desc)
                summary_parts = []
                if type_ or cat:
                    summary_parts.append(f"{type_ or ''} {cat or ''}".strip())
                if vendor:
                    summary_parts.append(f"Brand: {vendor}")
                if price and price != 'N/A':
                    summary_parts.append(f"Price: {price}")
                if desc:
                    summary_parts.append(desc[:40])
                summary = " | ".join([p for p in summary_parts if p])
                items.append({
                    "title": title,
                    "description": summary[:60],
                    "payload": str(product.get('id', 'unknown'))
                })
            
            return {
                "whatsapp_type": "interactive_list",
                "template": {
                    "template_args": [
                        "Available Products",
                        f"Found {len(products)} products for you:",
                        json.dumps(items)
                    ]
                },
                "products_data": products  # Store original products data
            }
            
        except Exception as e:
            logger.error(f"Failed to create product list: {e}")
            return {
                "whatsapp_type": "text",
                "message": "Unable to display products at the moment. Please try again later."
            }
    
    def create_product_gallery(self, products: List[Dict], title: str = "Product Gallery") -> List[Dict]:
        """
        Create multiple product cards for a gallery view.
        
        Args:
            products: List of product dictionaries
            title: Gallery title
        """
        messages = []
        
        # Add gallery header
        header_message = {
            "whatsapp_type": "text",
            "message": f"🛍️ {title}\n\nHere are our featured products:"
        }
        messages.append(header_message)
        
        # Add individual product cards
        for product in products[:5]:  # Limit to 5 products to avoid spam
            product_card = self.create_product_card(product)
            messages.append(product_card)
        
        return messages
    
    def create_buy_now_message(self, product: Dict) -> Dict:
        """
        Create a focused buy now message for a specific product.
        
        Args:
            product: Product dictionary
        """
        try:
            # Create a button template focused on buying
            template_id = "welcome___product_finder_flow"  # Using welcome template as base
            
            product_name = product.get('name', 'Product')
            product_id = product.get('id', 'PROD-001')
            price = product.get('price', 'N/A')
            
            template_args = [
                f"buy_now_{product_id}",      # {{1}} - Buy now action
                f"view_details_{product_id}", # {{2}} - View details action
                f"contact_support_{product_id}" # {{3}} - Contact support action
            ]
            
            return {
                "whatsapp_type": "buttonTemplate",
                "template": {
                    "template_id": template_id,
                    "template_args": template_args
                },
                "product_data": product
            }
            
        except Exception as e:
            logger.error(f"Failed to create buy now message: {e}")
            return self._create_fallback_product_message(product)
    
    def create_product_with_link(self, product: Dict) -> Dict:
        """
        Create a product message with a direct buy link.
        
        Args:
            product: Product dictionary with buy_url
        """
        try:
            if not product.get('buy_url'):
                logger.warning("No buy_url provided, creating standard product card")
                return self.create_product_card(product)
            
            # Create a text message with product info and link
            product_name = product.get('name', 'Product')
            price = product.get('price', 'N/A')
            description = product.get('description', '')
            buy_url = product.get('buy_url')
            
            message = f"""🛍️ **{product_name}**

💰 Price: {price}
📝 {description}

🛒 **Buy Now**: {buy_url}

Click the link above to purchase this product!"""
            
            return {
                "whatsapp_type": "text",
                "message": message
            }
            
        except Exception as e:
            logger.error(f"Failed to create product with link: {e}")
            return self._create_fallback_product_message(product)
    
    def _create_fallback_product_message(self, product: Dict) -> Dict:
        """Create a fallback text message when templates fail."""
        product_name = product.get('name', 'Product')
        price = product.get('price', 'N/A')
        description = product.get('description', '')
        
        message = f"""🛍️ **{product_name}**
💰 Price: {price}
📝 {description}

To purchase this product, please contact our support team."""
        
        return {
            "whatsapp_type": "text",
            "message": message
        }
    
    async def send_product_showcase(self, chat_id: str, product: Dict) -> bool:
        """
        Send a product showcase message.
        
        Args:
            chat_id: Recipient phone number
            product: Product dictionary
        """
        try:
            # Create product card
            product_message = self.create_product_card(product)
            # Send the message as a button template
            template = product_message.get("template", {})
            template_id = template.get("template_id")
            template_args = template.get("template_args", [])
            if template_id and template_args:
                return await self.client.send_button_template(chat_id, template_id, template_args)
            else:
                # Fallback to text
                return await self.client.send_text(chat_id, product_message.get("message", "Product info"))
        except Exception as e:
            logger.error(f"Error sending product showcase: {e}")
            return False
    
    async def send_product_list(self, chat_id: str, products: List[Dict]) -> bool:
        """
        Send a product list message. Only send interactive list if customer is existing.
        """
        try:
            # Check customer status
            status = self.utils.check_customer_status(chat_id)
            if status.get('status') == 'existing_customer':
                # Create product list (interactive)
                list_message = self.create_product_list(products)
                # Parse items for interactive list
                items = json.loads(list_message["template"]["template_args"][2])
                return await self.client.send_interactive_list(
                    chat_id,
                    list_message["template"]["template_args"][0],
                    list_message["template"]["template_args"][1],
                    items
                )
            else:
                # Fallback: send as a button template (first product)
                logger.info("Customer is new; sending product card as button template instead of interactive list.")
                if products:
                    return await self.send_product_showcase(chat_id, products[0])
                else:
                    return False
        except Exception as e:
            logger.error(f"Error sending product list: {e}")
            return False
    
    async def send_product_gallery(self, chat_id: str, products: List[Dict], title: str = "Product Gallery") -> bool:
        """
        Send a product gallery (multiple messages). Only send interactive/gallery if customer is existing.
        """
        try:
            status = self.utils.check_customer_status(chat_id)
            if status.get('status') == 'existing_customer':
                gallery_messages = self.create_product_gallery(products, title)
                success_count = 0
                for message in gallery_messages:
                    if message.get("whatsapp_type") == "buttonTemplate":
                        template = message.get("template", {})
                        template_id = template.get("template_id")
                        template_args = template.get("template_args", [])
                        if template_id and template_args:
                            success = await self.client.send_button_template(chat_id, template_id, template_args)
                        else:
                            success = await self.client.send_text(chat_id, message.get("message", "Product info"))
                    else:
                        success = await self.client.send_text(chat_id, message.get("message", "Product info"))
                    if success:
                        success_count += 1
                    else:
                        logger.warning(f"Failed to send gallery message: {message.get('whatsapp_type', 'unknown')}")
                logger.info(f"Product gallery sent: {success_count}/{len(gallery_messages)} messages successful")
                return success_count > 0
            else:
                logger.info("Customer is new; sending only the first product card as button template.")
                if products:
                    return await self.send_product_showcase(chat_id, products[0])
                else:
                    return False
        except Exception as e:
            logger.error(f"Error sending product gallery: {e}")
            return False
    
    async def send_product_with_link(self, chat_id: str, product: Dict) -> bool:
        """
        Send a product message with direct buy link.
        
        Args:
            chat_id: Recipient phone number
            product: Product dictionary with buy_url
        """
        try:
            # Create product with link message
            link_message = self.create_product_with_link(product)
            return await self.client.send_text(chat_id, link_message.get("message", "Product info"))
        except Exception as e:
            logger.error(f"Error sending product with link: {e}")
            return False
    
    async def send_custom_promo_card(self, chat_id: str, image_url: str, text: str, buttons: list) -> bool:
        """
        Send a custom promo card with image, text, and up to 3 buttons.
        buttons: List of dicts, e.g. [{"title": "Schedule Demo", "payload": "schedule_demo"}, ...]
        """
        template_id = "welcome___product_finder_flow"  # Replace with your actual template ID if different
        # Only send 3 arguments for 3 buttons (do not include text)
        template_args = [b["payload"] for b in buttons[:3]]
        while len(template_args) < 3:
            template_args.append("")
        return await self.client.send_button_template(chat_id, template_id, template_args)

    async def send_generic_promo_card(self, chat_id: str, image_url: str, name: str, business: str, buttons: list, template_id: str = "greet_with_options_01") -> bool:
        """
        Send a generic promo card with a header image, name, business, and 3 button payloads.
        - chat_id: WhatsApp number
        - image_url: URL for the header image
        - name: User's name
        - business: Business or context string
        - buttons: List of 3 payloads (strings)
        - template_id: Zoko template ID (default: greet_with_options_01)
        """
        # The template must have 6 variables: image, name, business, btn1, btn2, btn3
        template_args = [image_url, name, business] + buttons[:3]
        while len(template_args) < 6:
            template_args.append("")
        return await self.client.send_button_template(chat_id, template_id, template_args)

    async def send_affiliate_program_template(self, chat_id: str) -> bool:
        """
        Send the 'affiliate_program' button template to a WhatsApp user.
        Args:
            chat_id: WhatsApp number (string)
        Returns:
            bool: True if sent successfully, False otherwise
        """
        template_id = "affiliate_program"
        template_args = [
            "Register as new",
            "Payout questions",
            "Products promotion"
        ]
        return await self.client.send_button_template(chat_id, template_id, template_args)

    async def send_product_with_two_buttons(self, chat_id: str, product: dict) -> bool:
        """
        Send a product template with two buttons (Buy Now, View Details) using the 'product_with_two_buttons' template.
        Args:
            chat_id: WhatsApp number (string)
            product: Product dictionary
        Returns:
            bool: True if sent successfully, False otherwise
        """
        return await self.client.send_button_template(chat_id, "product_with_two_buttons", [
            product.get('image_url', 'https://via.placeholder.com/400x200?text=Product+Image'),
            product.get('name', 'Product'),
            "Buy Now",
            "View Details"
        ])

# Global showcase instance
product_showcase = ProductShowcase()

# Convenience functions
async def send_product_card(chat_id: str, product: Dict) -> bool:
    """Send a product card with image, name, and buy button."""
    return await product_showcase.send_product_showcase(chat_id, product)

async def send_product_list(chat_id: str, products: List[Dict]) -> bool:
    """Send a list of products."""
    return await product_showcase.send_product_list(chat_id, products)

async def send_product_gallery(chat_id: str, products: List[Dict], title: str = "Product Gallery") -> bool:
    """Send a product gallery."""
    return await product_showcase.send_product_gallery(chat_id, products, title)

async def send_product_with_link(chat_id: str, product: Dict) -> bool:
    """Send a product with direct buy link."""
    return await product_showcase.send_product_with_link(chat_id, product)

def create_product_card(product: Dict) -> Dict:
    """Create a product card message structure."""
    return product_showcase.create_product_card(product)

def create_product_list(products: List[Dict]) -> Dict:
    """Create a product list message structure."""
    return product_showcase.create_product_list(products)

async def send_custom_promo_card(chat_id: str, image_url: str, text: str, buttons: list) -> bool:
    """Standalone function for sending a custom promo card (for demo/manual use)."""
    return await product_showcase.send_custom_promo_card(chat_id, image_url, text, buttons)

async def send_generic_promo_card(chat_id: str, image_url: str, name: str, business: str, buttons: list, template_id: str = "greet_with_options_01") -> bool:
    """
    Send a generic promo card with a header image, name, business, and 3 button payloads.
    - chat_id: WhatsApp number
    - image_url: URL for the header image
    - name: User's name
    - business: Business or context string
    - buttons: List of 3 payloads (strings)
    - template_id: Zoko template ID (default: greet_with_options_01)
    """
    # The template must have 6 variables: image, name, business, btn1, btn2, btn3
    template_args = [image_url, name, business] + buttons[:3]
    while len(template_args) < 6:
        template_args.append("")
    return await product_showcase.client.send_button_template(chat_id, template_id, template_args)

async def send_affiliate_program_template(chat_id: str) -> bool:
    """
    Send the 'affiliate_program' button template to a WhatsApp user.
    Args:
        chat_id: WhatsApp number (string)
    Returns:
        bool: True if sent successfully, False otherwise
    """
    return await product_showcase.send_affiliate_program_template(chat_id)

async def send_product_with_two_buttons(chat_id: str, product: dict) -> bool:
    """
    Send a product template with two buttons (Buy Now, View Details) using the 'product_with_two_buttons' template.
    Args:
        chat_id: WhatsApp number (string)
        product: Product dictionary
    Returns:
        bool: True if sent successfully, False otherwise
    """
    return await product_showcase.send_product_with_two_buttons(chat_id, product) 