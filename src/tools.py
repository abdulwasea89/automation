import json
import re
from typing import List, Dict
from agents import function_tool
from src.logger import get_logger, log_database, log_error
from src.deps import db
from src.config import settings
import requests
from src.translation_utils import get_translation
# Remove: from src.products import load_products_from_json
# Remove: products = load_products_from_json()
# Ensure all product fetching is from Firestore (db) only
from src.semantic_search import search_products_best

# Remove: semantic_engine = SemanticSearchEngine(products) # This line is removed as per the edit hint

logger = get_logger("tools")

class ProductDatabase:
    """Database interface for product management."""
    COLLECTION = "products"

    @staticmethod
    def search_products(query: str, limit: int = 10) -> List[Dict]:
        """Search products by keywords, title, or name (optimized with Firestore queries)."""
        if db is None:
            log_database("SEARCH", query=query, error="database_not_available")
            logger.warning("Database not available")
            return []
        try:
            # Guard: limit must be at least 1
            if not isinstance(limit, int) or limit < 1:
                limit = 10
            
            # Clean and normalize the query
            def normalize(s):
                return re.sub(r'\s+', ' ', str(s or '').lower().strip())
            
            query_clean = re.sub(r'<.*?>', '', query)
            query_clean = query_clean.replace('🏡', '').replace('\n', ' ').replace('\r', ' ')
            query_clean = query_clean.split('<br/>')[0]
            query_clean = query_clean.strip()
            
            log_database("SEARCH", query=query_clean, limit=limit, original_query=query)
            
            if not query_clean:
                # Return limited products for empty query
                docs = db.collection(ProductDatabase.COLLECTION).limit(limit).stream()
                results = [ProductDatabase._format_for_whatsapp(doc.to_dict()) for doc in docs]
                log_database("SEARCH_EMPTY", query="empty_query", results_count=len(results), limit=limit)
                return results
            
            query_lower = query_clean.lower()
            matching_products = []
            
            # 1. Try exact match on title (most efficient)
            title_query = db.collection(ProductDatabase.COLLECTION).where("title", "==", query_clean).limit(1).stream()
            for doc in title_query:
                formatted = ProductDatabase._format_for_whatsapp(doc.to_dict())
                formatted["id"] = str(doc.to_dict().get("id", ""))
                formatted["payload"] = str(doc.to_dict().get("id", ""))
                log_database("SEARCH_EXACT", query=query_clean, match_type="exact_title", results_count=1)
                return [formatted]
            
            # 2. Try prefix search on title (efficient with indexing)
            title_prefix = query_clean + "\uf8ff"
            title_query = db.collection(ProductDatabase.COLLECTION).where("title", ">=", query_clean).where("title", "<=", title_prefix).limit(limit).stream()
            for doc in title_query:
                product_data = doc.to_dict()
                title = str(product_data.get("title", "")).lower()
                if query_lower in title:
                    formatted = ProductDatabase._format_for_whatsapp(product_data)
                    formatted["id"] = str(product_data.get("id", ""))
                    formatted["payload"] = str(product_data.get("id", ""))
                    matching_products.append(formatted)
                    if len(matching_products) >= limit:
                        break
            
            # 3. If not enough results, try name field
            if len(matching_products) < limit:
                name_prefix = query_clean + "\uf8ff"
                name_query = db.collection(ProductDatabase.COLLECTION).where("name", ">=", query_clean).where("name", "<=", name_prefix).limit(limit - len(matching_products)).stream()
                for doc in name_query:
                    product_data = doc.to_dict()
                    name = str(product_data.get("name", "")).lower()
                    if query_lower in name:
                        formatted = ProductDatabase._format_for_whatsapp(product_data)
                        formatted["id"] = str(product_data.get("id", ""))
                        formatted["payload"] = str(product_data.get("id", ""))
                        matching_products.append(formatted)
                        if len(matching_products) >= limit:
                            break
            
            # 4. Fallback: limited scan for fuzzy matching (only if needed)
            if len(matching_products) < 3:  # Only if we have very few results
                docs = db.collection(ProductDatabase.COLLECTION).limit(50).stream()  # Limited scan
                for doc in docs:
                    if len(matching_products) >= limit:
                        break
                    product_data = doc.to_dict()
                    title = str(product_data.get("title", "")).lower()
                    name = str(product_data.get("name", "")).lower()
                    body_html = str(product_data.get("body_html", "") or "").lower()
                    
                    if (query_lower in title or query_lower in name or 
                        any(word in body_html for word in query_lower.split() if len(word) > 2)):
                        formatted = ProductDatabase._format_for_whatsapp(product_data)
                        formatted["id"] = str(product_data.get("id", ""))
                        formatted["payload"] = str(product_data.get("id", ""))
                        matching_products.append(formatted)
            
            log_database("SEARCH_COMPLETE", query=query_clean, results_count=len(matching_products), limit=limit)
            return matching_products[:limit]
            
        except Exception as e:
            log_error("DATABASE_SEARCH", str(e), query=query, limit=limit)
            logger.error(f"Search failed for '{query}': {str(e)}")
            return []

    @staticmethod
    def _format_for_whatsapp(product: Dict) -> Dict:
        """Format product data for WhatsApp templates with simple image handling."""
        # Get image URL with fallback
        image_url = product.get("images", [{}])[0].get("src") or "https://via.placeholder.com/400x300?text=Product"
        
        # Simple validation without HTTP requests
        if not image_url or image_url == "https://via.placeholder.com/400x300?text=Product":
            image_url = "https://raw.githubusercontent.com/Nignanfatao/zok/main/Zokou.jpg"
        
        price = product.get("variants", [{}])[0].get("price", "Contact for price")
        # Use body_html as description, fallback to empty string
        description = product.get("body_html", "")[:200]
        return {
            "id": product.get("id", ""),
            "title": product.get("title", "Product"),
            "description": description,
            "price": price,
            "image_url": image_url,
            "url": f"https://{settings.SHOPIFY_STORE_NAME}.myshopify.com/products/{product.get('handle', '')}"
        }

def search_database_func(action: str, query: str = "", property_id: str = "", limit: int = 10, lang: str = "en") -> str:
    """Enhanced database search function."""
    try:
        log_database("FUNCTION_CALL", query=f"action={action}", property_id=property_id, limit=limit)
        
        if action == "search":
            products = ProductDatabase.search_products(query, limit)
            if not products:
                log_database("SEARCH_RESULT", query="no_products_found", limit=limit)
                return json.dumps({"success": False, "message": get_translation("no_products", lang), "products": []})
            log_database("SEARCH_RESULT", query="products_found", count=len(products), limit=limit)
            return json.dumps({"success": True, "products": products})
        elif action == "get_by_id":
            # Use robust matching for property_id (by id, title, or name)
            products = ProductDatabase.search_products(property_id, 1)
            if not products:
                log_database("GET_BY_ID_RESULT", property_id=property_id)
                return json.dumps({"success": False, "message": get_translation("no_products", lang), "products": []})
            log_database("GET_BY_ID_RESULT", property_id=property_id, count=len(products))
            return json.dumps({"success": True, "products": products})
        
        log_error("DATABASE_ACTION", f"Invalid action '{action}'")
        return json.dumps({"success": False, "message": get_translation("no_products", lang)})
    except Exception as e:
        log_error("DATABASE_FUNCTION", str(e), action=action, query=query, property_id=property_id)
        logger.error(f"Database search failed: {str(e)}")
        return json.dumps({"success": False, "message": get_translation("no_products", lang), "products": []})

@function_tool
def search_database(action: str, query: str = "", property_id: str = "", limit: int = 10, lang: str = "en") -> str:
    """Consolidated database search tool."""
    return search_database_func(action, query, property_id, limit, lang)

@function_tool
def get_general_product_info() -> str:
    """
    Returns a general description of the business's product categories.
    """
    return (
        "We offer a wide range of modular architectural products, including:\n\n"
        "* Tiny Houses & Family Homes (with versatile L- and U-shaped layouts)\n"
        "* Swimming Pools & Natural Ponds\n"
        "* Outdoor Spas & Wellness Areas\n"
        "* Summer Houses & Garden Rooms\n"
        "* Commercial Buildings (like coffee shops and more)\n"
        "* Construction Plans in PDF, DWG, IFC, and GLB formats\n"
        "* Free Downloads (budget plans and sample units)\n"
        "* MEP & BIM-ready files\n"
        "* Augmented Reality previews & cost estimators\n\n"
        "If you’d like to know more about any of these products or need additional details, just let me know!"
    )

def search_products_semantic(query, top_k=5, lang="en"):
    # Fetch products from Firestore
    if db is None:
        logger.warning("Database not available for semantic search")
        return []
    docs = db.collection(ProductDatabase.COLLECTION).stream()
    products = [doc.to_dict() for doc in docs]
    return search_products_best(query, products, top_k=top_k)

def is_general_product_info_query(text: str) -> bool:
    text = text.strip().lower()
    # Fuzzy/keyword-based detection
    if "product" in text and any(kw in text for kw in ["what", "type", "kind", "offer", "have", "do you"]):
        return True
    GENERAL_PRODUCT_QUERIES = [
        "what products do you have",
        "what do you offer",
        "what can i buy",
        "what do you sell",
        "what are your products",
        "what type of products do you have",
        "what kind of products do you have",
        "what types of products do you offer",
        "what products are available"
    ]
    return text in GENERAL_PRODUCT_QUERIES
async def send_text_message(chat_id: str, text: str):
    from src.zoko_client import zoko_client
    await zoko_client.send_text(chat_id, text)

async def send_interactive_list_message(chat_id: str, header: str, body: str, items: list):
    from src.zoko_client import zoko_client
    await zoko_client.send_interactive_list(chat_id, header, body, items)
