import re
import json
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

from agents import function_tool
from src.logger import get_logger
from src.config import settings
from src.deps import db

logger = get_logger("tools")

class ProductDatabase:
    """Clean, production-ready database interface for product management."""
    
    COLLECTION = "products"
    
    @staticmethod
    def search_products(query: str, limit: int = 10) -> List[Dict]:
        """
        Search products by keywords in title, description, type, or tags.
        Returns formatted products ready for WhatsApp templates.
        """
        if db is None:
            logger.warning("Database not available")
            return []
        
        try:
            query_lower = query.lower().strip()
            if not query_lower:
                return []
            
            products_ref = db.collection(ProductDatabase.COLLECTION)
            docs = products_ref.stream()
            
            matching_products = []
            for doc in docs:
                product_data = doc.to_dict()
                
                # Search in multiple fields
                searchable_text = " ".join([
                    product_data.get("title", ""),
                    product_data.get("body_html", ""),
                    product_data.get("product_type", ""),
                    product_data.get("tags", ""),
                    product_data.get("vendor", "")
                ]).lower()
                
                # Check for exact matches first (higher priority)
                if query_lower in searchable_text:
                    # Format product for WhatsApp
                    formatted_product = ProductDatabase._format_for_whatsapp(product_data)
                    matching_products.append(formatted_product)
                    
                    if len(matching_products) >= limit:
                        break
                else:
                    # Check for partial word matches (e.g., "LYNX Product" should match "LYNX 116")
                    query_words = query_lower.split()
                    searchable_words = searchable_text.split()
                    
                    # Check if any query word matches any searchable word
                    for query_word in query_words:
                        for searchable_word in searchable_words:
                            if query_word in searchable_word or searchable_word in query_word:
                                # Format product for WhatsApp
                                formatted_product = ProductDatabase._format_for_whatsapp(product_data)
                                matching_products.append(formatted_product)
                                
                                if len(matching_products) >= limit:
                                    break
                                break  # Found a match for this query word, move to next
                    if len(matching_products) >= limit:
                        break
            
            logger.info(f"Found {len(matching_products)} products matching '{query}'")
            return matching_products
            
        except Exception as e:
            logger.error(f"Search failed for '{query}': {str(e)}")
            return []

    @staticmethod
    def get_all_products(limit: int = 20) -> List[Dict]:
        """Get all products with WhatsApp formatting."""
        if db is None:
            logger.warning("Database not available")
            return []
        
        try:
            products_ref = db.collection(ProductDatabase.COLLECTION)
            docs = products_ref.limit(limit).stream()
            
            products = []
            for doc in docs:
                product_data = doc.to_dict()
                formatted_product = ProductDatabase._format_for_whatsapp(product_data)
                products.append(formatted_product)
            
            logger.info(f"Retrieved {len(products)} products")
            return products
            
        except Exception as e:
            logger.error(f"Failed to get products: {str(e)}")
            return []

    @staticmethod
    def _format_for_whatsapp(product: Dict) -> Dict:
        """Format product data for WhatsApp templates."""
        # Get image URL
        image_url = None
        if product.get("images") and isinstance(product["images"], list) and product["images"]:
            image_url = product["images"][0].get("src")
        elif product.get("image") and product["image"].get("src"):
            image_url = product["image"]["src"]
        
        # Fallback image
        if not image_url:
            image_url = "https://via.placeholder.com/400x300?text=Product"
        
        # Get price
        variants = product.get("variants", [])
        price = variants[0].get("price", "Contact for price") if variants else "Contact for price"
        
        # Clean description
        body_html = product.get("body_html", "")
        description = re.sub(r'<[^>]+>', '', body_html)[:200]
        if len(re.sub(r'<[^>]+>', '', body_html)) > 200:
            description += "..."
        
        # Build URL
        handle = product.get("handle", "")
        url = f"https://{settings.SHOPIFY_STORE_NAME}.myshopify.com/products/{handle}"
        
        return {
            "id": product.get("id", ""),
            "title": product.get("title", "Product"),
            "description": description,
            "price": price,
            "image_url": image_url,
            "url": url,
            "product_type": product.get("product_type", ""),
            "tags": product.get("tags", ""),
            "handle": handle,
            "raw_data": product  # Keep original data for advanced formatting
        }

# Regular function for direct calls (used in tests)
def search_database_func(action: str, query: str = "", property_id: str = "", limit: int = 10) -> str:
    """
    Regular function version of search_database for direct calls.
    
    Args:
        action: The type of search action ("search", "browse_all", "get_details")
        query: Search terms for property search (e.g., "3 bedroom apartment", "villa with pool")
        property_id: Specific property ID for detailed view
        limit: Maximum number of results to return
    
    Returns:
        JSON string with search results and WhatsApp template data
    """
    logger.info(f"Database search action: {action}, query: {query}, property_id: {property_id}")
    
    try:
        if action == "search":
            if not query.strip():
                return json.dumps({
                    "success": False,
                    "message": "Please provide a search query",
                    "products": [],
                    "count": 0,
                    "handoff_required": False
                })
            
            products = ProductDatabase.search_products(query, limit)
            
            if not products:
                return json.dumps({
                    "success": True,
                    "message": f"No products found matching '{query}'. Try different keywords or browse all products.",
                    "products": [],
                    "count": 0,
                    "suggestions": ["electronics", "clothing", "accessories", "home", "gaming"],
                    "handoff_required": False
                })
            
            # Format for WhatsApp templates
            if len(products) == 1:
                # Single product - use rich template with image
                product = products[0]
                template_data = {
                    "template_id": "zoko_upsell_product_01",
                    "template_args": [
                        product["image_url"],
                        product["title"],
                        f"PROD-{product['id']}",
                        "view_details_payload"
                    ]
                }
                whatsapp_type = "buttonTemplate"
            else:
                # Multiple products - use interactive list
                items = []
                for product in products[:10]:
                    title = product["title"][:20] if len(product["title"]) > 20 else product["title"]
                    items.append({
                        "title": title,
                        "description": f"{product['price']} - {product['product_type']}",
                        "payload": f"view_{product['id']}"
                    })
                
                template_data = {
                    "template_id": "property_list_interactive",
                    "template_args": [
                        "Available Products",
                        f"Found {len(products)} products matching '{query}'",
                        json.dumps(items)
                    ]
                }
                whatsapp_type = "interactive_list"
            
            return json.dumps({
                "success": True,
                "message": f"Found {len(products)} products matching '{query}'",
                "products": products,
                "count": len(products),
                "template": template_data,
                "whatsapp_type": whatsapp_type,
                "handoff_required": False
            })
            
        elif action == "browse_all":
            products = ProductDatabase.get_all_products(limit)
            
            if not products:
                return json.dumps({
                    "success": True,
                    "message": "No products available at the moment. Please check back later.",
                    "products": [],
                    "count": 0,
                    "handoff_required": False
                })
            
            # Create interactive list for multiple products
            items = []
            for product in products:
                title = product["title"][:20] if len(product["title"]) > 20 else product["title"]
                items.append({
                    "title": title,
                    "description": f"{product['price']} - {product['product_type']}",
                    "payload": f"view_{product['id']}"
                })
            
            template_data = {
                "template_id": "property_list_interactive",
                "template_args": [
                    "All Available Products",
                    f"Browse our {len(products)} products",
                    json.dumps(items)
                ]
            }
            
            return json.dumps({
                "success": True,
                "message": f"Here are all {len(products)} available products:",
                "products": products,
                "count": len(products),
                "template": template_data,
                "whatsapp_type": "interactive_list",
                "handoff_required": False
            })
            
        elif action == "get_details":
            if not property_id.strip():
                return json.dumps({
                    "success": False,
                    "message": "Please provide a product ID",
                    "product": None,
                    "handoff_required": False
                })
            
            # Search for the specific product
            products = ProductDatabase.search_products(property_id, limit=1)
            
            if not products:
                return json.dumps({
                    "success": False,
                    "message": f"Product with ID '{property_id}' not found",
                    "product": None,
                    "handoff_required": True,
                    "handoff_reason": "Product not found - may need human assistance"
                })
            
            product = products[0]
            
            # Create detailed template using button template
            template_data = {
                "template_id": "zoko_upsell_product_01",
                "template_args": [
                    product["image_url"],
                    product["title"],
                    f"PROD-{product['id']}",
                    "contact_agent_payload"
                ]
            }
            
            return json.dumps({
                "success": True,
                "message": f"Here are the details for {product['title']}:",
                "product": product,
                "template": template_data,
                "whatsapp_type": "buttonTemplate",
                "handoff_required": False
            })
            
        else:
            return json.dumps({
                "success": False,
                "message": f"Invalid action '{action}'. Use 'search', 'browse_all', or 'get_details'",
                "products": [],
                "count": 0,
                "handoff_required": False
            })
            
    except Exception as e:
        logger.error(f"Database search failed: {str(e)}")
        return json.dumps({
            "success": False,
            "message": "Sorry, I'm having trouble accessing the database right now.",
            "products": [],
            "count": 0,
            "handoff_required": True,
            "handoff_reason": "Database error - technical assistance needed"
        })

@function_tool
def search_database(action: str, query: str = "", property_id: str = "", limit: int = 10) -> str:
    """
    Consolidated database search tool that handles search, browse, and details operations.
    
    Args:
        action: The type of search action ("search", "browse_all", "get_details")
        query: Search terms for product search (e.g., "LYNX Product", "iPhone", "gaming laptop")
        property_id: Specific product ID for detailed view
        limit: Maximum number of results to return
    
    Returns:
        JSON string with search results and WhatsApp template data
    """
    return search_database_func(action, query, property_id, limit)

# Backward compatibility functions
@function_tool
def search_products(query: str) -> str:
    """Backward compatibility: Search for products."""
    return search_database("search", query=query)

@function_tool
def get_all_products() -> str:
    """Backward compatibility: Get all products."""
    return search_database("browse_all")

@function_tool
def get_product_details(product_id: str) -> str:
    """Backward compatibility: Get product details."""
    return search_database("get_details", product_id=product_id)
