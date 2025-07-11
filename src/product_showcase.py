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
            # Use buttonTemplate for product showcase (not richTemplate)
            image_url = product.get('image_url', 'https://via.placeholder.com/400x200?text=Product+Image')
            product_name = product.get('name', 'Product')
            product_id = product.get('id', 'PROD-001')
            buy_action = product.get('buy_payload', 'buy_now_payload')
            if product.get('buy_url'):
                buy_action = f"buy_url_{product_id}"
            template_args = [image_url, product_name, product_id, buy_action]
            # If your template expects only 3 args, trim to 3
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
                title = product.get('name', 'Product')[:24]  # 24 char limit
                description = f"{product.get('price', 'N/A')} - {product.get('description', '')[:50]}"
                
                items.append({
                    "title": title,
                    "description": description,
                    "payload": f"view_product_{product.get('id', 'unknown')}"
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
    
    def send_product_showcase(self, chat_id: str, product: Dict) -> bool:
        """
        Send a product showcase message.
        
        Args:
            chat_id: Recipient phone number
            product: Product dictionary
        """
        try:
            # Create product card
            product_message = self.create_product_card(product)
            
            # Send the message
            success = self.client.send_rich_message(chat_id, product_message)
            
            if success:
                logger.info(f"Product showcase sent successfully for {product.get('name', 'Product')}")
            else:
                logger.error(f"Failed to send product showcase for {product.get('name', 'Product')}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending product showcase: {e}")
            return False
    
    def send_product_list(self, chat_id: str, products: List[Dict]) -> bool:
        """
        Send a product list message. Only send interactive list if customer is existing.
        """
        try:
            # Check customer status
            status = self.utils.check_customer_status(chat_id)
            if status.get('status') == 'existing_customer':
                # Create product list (interactive)
                list_message = self.create_product_list(products)
                success = self.client.send_rich_message(chat_id, list_message)
                if success:
                    logger.info(f"Product list sent successfully with {len(products)} products (interactive)")
                else:
                    logger.error(f"Failed to send product list (interactive)")
                return success
            else:
                # Fallback: send as a button template (first product)
                logger.info("Customer is new; sending product card as button template instead of interactive list.")
                if products:
                    return self.send_product_showcase(chat_id, products[0])
                else:
                    return False
        except Exception as e:
            logger.error(f"Error sending product list: {e}")
            return False
    
    def send_product_gallery(self, chat_id: str, products: List[Dict], title: str = "Product Gallery") -> bool:
        """
        Send a product gallery (multiple messages). Only send interactive/gallery if customer is existing.
        """
        try:
            status = self.utils.check_customer_status(chat_id)
            if status.get('status') == 'existing_customer':
                gallery_messages = self.create_product_gallery(products, title)
                success_count = 0
                for message in gallery_messages:
                    success = self.client.send_rich_message(chat_id, message)
                    if success:
                        success_count += 1
                    else:
                        logger.warning(f"Failed to send gallery message: {message.get('whatsapp_type', 'unknown')}")
                logger.info(f"Product gallery sent: {success_count}/{len(gallery_messages)} messages successful")
                return success_count > 0
            else:
                logger.info("Customer is new; sending only the first product card as button template.")
                if products:
                    return self.send_product_showcase(chat_id, products[0])
                else:
                    return False
        except Exception as e:
            logger.error(f"Error sending product gallery: {e}")
            return False
    
    def send_product_with_link(self, chat_id: str, product: Dict) -> bool:
        """
        Send a product message with direct buy link.
        
        Args:
            chat_id: Recipient phone number
            product: Product dictionary with buy_url
        """
        try:
            # Create product with link message
            link_message = self.create_product_with_link(product)
            
            # Send the message
            success = self.client.send_rich_message(chat_id, link_message)
            
            if success:
                logger.info(f"Product with link sent successfully for {product.get('name', 'Product')}")
            else:
                logger.error(f"Failed to send product with link")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending product with link: {e}")
            return False
    
    def send_custom_promo_card(self, chat_id: str, image_url: str, text: str, buttons: list) -> bool:
        """
        Send a custom promo card with image, text, and up to 3 buttons.
        buttons: List of dicts, e.g. [{"title": "Schedule Demo", "payload": "schedule_demo"}, ...]
        """
        template_id = "welcome___product_finder_flow"  # Replace with your actual template ID if different
        # Only send 3 arguments for 3 buttons (do not include text)
        template_args = [b["payload"] for b in buttons[:3]]
        while len(template_args) < 3:
            template_args.append("")
        message = {
            "whatsapp_type": "buttonTemplate",
            "template": {
                "template_id": template_id,
                "template_args": template_args
            }
        }
        return self.client.send_rich_message(chat_id, message)

    def send_generic_promo_card(self, chat_id: str, image_url: str, name: str, business: str, buttons: list, template_id: str = "greet_with_options_01") -> bool:
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
        message = {
            "whatsapp_type": "buttonTemplate",
            "template": {
                "template_id": template_id,
                "template_args": template_args
            }
        }
        return self.client.send_rich_message(chat_id, message)

# Global showcase instance
product_showcase = ProductShowcase()

# Convenience functions
def send_product_card(chat_id: str, product: Dict) -> bool:
    """Send a product card with image, name, and buy button."""
    return product_showcase.send_product_showcase(chat_id, product)

def send_product_list(chat_id: str, products: List[Dict]) -> bool:
    """Send a list of products."""
    return product_showcase.send_product_list(chat_id, products)

def send_product_gallery(chat_id: str, products: List[Dict], title: str = "Product Gallery") -> bool:
    """Send a product gallery."""
    return product_showcase.send_product_gallery(chat_id, products, title)

def send_product_with_link(chat_id: str, product: Dict) -> bool:
    """Send a product with direct buy link."""
    return product_showcase.send_product_with_link(chat_id, product)

def create_product_card(product: Dict) -> Dict:
    """Create a product card message structure."""
    return product_showcase.create_product_card(product)

def create_product_list(products: List[Dict]) -> Dict:
    """Create a product list message structure."""
    return product_showcase.create_product_list(products)

def send_custom_promo_card(chat_id: str, image_url: str, text: str, buttons: list) -> bool:
    """Standalone function for sending a custom promo card (for demo/manual use)."""
    return product_showcase.send_custom_promo_card(chat_id, image_url, text, buttons)

def send_generic_promo_card(chat_id: str, image_url: str, name: str, business: str, buttons: list, template_id: str = "greet_with_options_01") -> bool:
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
    message = {
        "whatsapp_type": "buttonTemplate",
        "template": {
            "template_id": template_id,
            "template_args": template_args
        }
    }
    return product_showcase.client.send_rich_message(chat_id, message) 