import json
from typing import List, Dict
from agents import function_tool
from src.logger import get_logger
from src.deps import db
from src.config import settings

logger = get_logger("tools")

class ProductDatabase:
    """Database interface for product management."""
    COLLECTION = "products"
    
    @staticmethod
    def _load_products_from_json():
        """Load products from products.json file as fallback."""
        try:
            import json
            import os
            
            json_path = os.path.join(os.path.dirname(__file__), '..', 'products.json')
            if not os.path.exists(json_path):
                logger.warning(f"products.json not found at {json_path}")
                return []
            
            with open(json_path, 'r', encoding='utf-8') as f:
                products = json.load(f)
            
            logger.info(f"Loaded {len(products)} products from products.json")
            return products
            
        except Exception as e:
            logger.error(f"Failed to load products from JSON: {str(e)}")
            return []

    @staticmethod
    def search_products(query: str, limit: int = 10) -> List[Dict]:
        """Search products by keywords."""
        if db is None:
            logger.warning("Database not available")
            return []
        try:
            query_lower = query.lower().strip()
            products_ref = db.collection(ProductDatabase.COLLECTION)
            docs = products_ref.stream()
            matching_products = []
            all_products = []
            
            # First, collect all products for logging
            for doc in docs:
                product_data = doc.to_dict()
                all_products.append(product_data)
            
            logger.info(f"Found {len(all_products)} total products in database")
            
            # If no products in database, return [] and log
            if not all_products:
                logger.warning("No products found in database")
                return []
            
            # Search through database products
            for product_data in all_products:
                searchable_text = " ".join([
                    product_data.get("title", ""),
                    product_data.get("body_html", ""),
                    product_data.get("product_type", ""),
                    product_data.get("tags", "")
                ]).lower()
                
                # More flexible matching
                if (query_lower in searchable_text or 
                    any(word in searchable_text for word in query_lower.split()) or
                    (query_lower in ["house", "houses"] and "house" in searchable_text) or
                    (query_lower in ["bedroom", "bedrooms"] and "bedroom" in searchable_text)):
                    
                    matching_products.append(ProductDatabase._format_for_whatsapp(product_data))
                    if len(matching_products) >= limit:
                        break
            
            logger.info(f"Found {len(matching_products)} matching products for query '{query}'")
            return matching_products
            
        except Exception as e:
            logger.error(f"Search failed for '{query}': {str(e)}")
            return []

    @staticmethod
    def _format_for_whatsapp(product: Dict) -> Dict:
        """Format product data for WhatsApp templates."""
        image_url = product.get("images", [{}])[0].get("src") or "https://via.placeholder.com/400x300?text=Product"
        price = product.get("variants", [{}])[0].get("price", "Contact for price")
        description = product.get("body_html", "")[:200]
        return {
            "id": product.get("id", ""),
            "title": product.get("title", "Product"),
            "description": description,
            "price": price,
            "image_url": image_url,
            "url": f"https://{settings.SHOPIFY_STORE_NAME}.myshopify.com/products/{product.get('handle', '')}"
        }

def search_database_func(action: str, query: str = "", property_id: str = "", limit: int = 10) -> str:
    """Enhanced database search function."""
    try:
        if action == "search":
            products = ProductDatabase.search_products(query, limit)
            if not products:
                return json.dumps({"success": False, "message": "No products found", "products": []})
            return json.dumps({"success": True, "products": products})
        return json.dumps({"success": False, "message": f"Invalid action '{action}'"})
    except Exception as e:
        logger.error(f"Database search failed: {str(e)}")
        return json.dumps({"success": False, "message": "Database error", "products": []})

@function_tool
def search_database(action: str, query: str = "", property_id: str = "", limit: int = 10) -> str:
    """Consolidated database search tool."""
    return search_database_func(action, query, property_id, limit)