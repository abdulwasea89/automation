import json
import re
from typing import List, Dict
from agents import function_tool
from src.logger import get_logger
from src.deps import db
from src.config import settings
import requests

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
        """Search products by keywords, title, or name (robust, case-insensitive, partial match)."""
        if db is None:
            logger.warning("Database not available")
            return []
        try:
            # Guard: limit must be at least 1
            if not isinstance(limit, int) or limit < 1:
                limit = 10
            # Normalize and clean the query
            def normalize(s):
                return re.sub(r'\s+', ' ', str(s or '').lower().strip())
            query_norm = normalize(query)
            query_clean = re.sub(r'<.*?>', '', query)
            query_clean = query_clean.replace('🏡', '').replace('\n', ' ').replace('\r', ' ')
            query_clean = query_clean.split('<br/>')[0]
            query_clean = query_clean.strip()
            query_lower = query_clean.lower()
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
            
            # If query is empty, return all products up to the limit
            if not query_clean:
                logger.info("No query provided, returning all products up to the limit.")
                return [ProductDatabase._format_for_whatsapp(p) for p in all_products[:limit]]
            
            # 1. Try exact match on id, title, or name (normalized)
            for product_data in all_products:
                id_str = normalize(product_data.get("id", ""))
                title_str = normalize(product_data.get("title", ""))
                name_str = normalize(product_data.get("name", ""))
                if (
                    query_norm == id_str or
                    query_norm == title_str or
                    query_norm == name_str
                ):
                    formatted = ProductDatabase._format_for_whatsapp(product_data)
                    formatted["id"] = str(product_data.get("id", ""))
                    formatted["payload"] = str(product_data.get("id", ""))
                    logger.info(f"Exact match found for query '{query}': {formatted['title']}")
                    return [formatted]
            
            # 2. Partial/fuzzy matching as before
            for product_data in all_products:
                # Clean and normalize product fields
                title = str(product_data.get("title", "")).strip()
                name = str(product_data.get("name", "")).strip()
                title_lower = title.lower()
                name_lower = name.lower()
                # Remove HTML, emojis, etc
                title_clean = re.sub(r'<.*?>', '', title).replace('🏡', '').strip()
                name_clean = re.sub(r'<.*?>', '', name).replace('🏡', '').strip()
                title_clean_lower = title_clean.lower()
                name_clean_lower = name_clean.lower()
                # Ensure all fields are strings
                body_html = str(product_data.get("body_html", "") or "")
                product_type = str(product_data.get("product_type", "") or "")
                tags = str(product_data.get("tags", "") or "")
                searchable_text = " ".join([
                    title_clean,
                    name_clean,
                    body_html,
                    product_type,
                    tags
                ]).lower()
                # Robust matching: exact, partial, and substring for title and name
                if (
                    query_lower in title_lower or
                    query_lower in name_lower or
                    query_lower in title_clean_lower or
                    query_lower in name_clean_lower or
                    query_lower in searchable_text or
                    any(word in searchable_text for word in query_lower.split()) or
                    (query_lower in ["house", "houses"] and "house" in searchable_text) or
                    (query_lower in ["bedroom", "bedrooms"] and "bedroom" in searchable_text)
                ):
                    formatted = ProductDatabase._format_for_whatsapp(product_data)
                    formatted["id"] = str(product_data.get("id", ""))
                    formatted["payload"] = str(product_data.get("id", ""))
                    matching_products.append(formatted)
                    if len(matching_products) >= limit:
                        break
            logger.info(f"Found {len(matching_products)} matching products for query '{query}'")
            return matching_products
        except Exception as e:
            logger.error(f"Search failed for '{query}': {str(e)}")
            return []

    @staticmethod
    def _format_for_whatsapp(product: Dict) -> Dict:
        """Format product data for WhatsApp templates with image URL validation."""
        def validate_image_url(url):
            try:
                resp = requests.head(url, allow_redirects=True, timeout=5)
                if resp.status_code != 200:
                    return False, "Image URL not accessible"
                content_type = resp.headers.get("Content-Type", "")
                if not (content_type.startswith("image/jpeg") or content_type.startswith("image/png")):
                    return False, "Unsupported image format"
                content_length = int(resp.headers.get("Content-Length", 0))
                if content_length > 5 * 1024 * 1024:
                    return False, "Image too large"
                return True, "OK"
            except Exception as e:
                return False, str(e)

        image_url = product.get("images", [{}])[0].get("src") or "https://via.placeholder.com/400x300?text=Product"
        is_valid, reason = validate_image_url(image_url)
        if not is_valid:
            logger.warning(f"Image URL '{image_url}' invalid for WhatsApp: {reason}. Using fallback.")
            image_url = "https://raw.githubusercontent.com/Nignanfatao/zok/main/Zokou.jpg"
        logger.info(f"Final image URL sent to WhatsApp: {image_url}")
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
        elif action == "get_by_id":
            # Use robust matching for property_id (by id, title, or name)
            products = ProductDatabase.search_products(property_id, 1)
            if not products:
                return json.dumps({"success": False, "message": f"No product found for '{property_id}'", "products": []})
            return json.dumps({"success": True, "products": products})
        return json.dumps({"success": False, "message": f"Invalid action '{action}'"})
    except Exception as e:
        logger.error(f"Database search failed: {str(e)}")
        return json.dumps({"success": False, "message": "Database error", "products": []})

@function_tool
def search_database(action: str, query: str = "", property_id: str = "", limit: int = 10) -> str:
    """Consolidated database search tool."""
    return search_database_func(action, query, property_id, limit)