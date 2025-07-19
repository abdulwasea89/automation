import json
from typing import Dict, List
from agents import function_tool
from src.logger import get_logger, log_agent, log_error
import re
from src.translation_utils import get_translation
from src.product_loader import product_loader
from collections import defaultdict

logger = get_logger("handoff_tools")

def classify_query_type(query: str) -> str:
    q = query.lower().strip()
    # Interactive list triggers
    interactive_keywords = [
        "all", "list", "show all", "show me all", "display all", "see all", "give me all", "everything", "more", "options"
    ]
    if any(kw in q for kw in interactive_keywords):
        return "interactive_list"
    # Product send triggers
    product_keywords = [
        "i want", "i need", "need", "want", "this product", "show this product", "bedroom", "rooms", "villa", "apartment", "house", "home", "luxury", "single-family"
    ]
    if any(kw in q for kw in product_keywords) or any(char.isdigit() for char in q):
        return "product_send"
    if q.startswith("what") or q.startswith("do you have") or q.startswith("can i get") or q.endswith("?"):
        return "general_question"
    if len(q.split()) <= 4:
        return "product_send"
    return "general_question"

def strip_html(text):
    return re.sub('<[^<]+?>', '', text or '')

def safe_field(val, maxlen, fallback="-"):
    if not val or not str(val).strip():
        return fallback
    return str(val).strip()[:maxlen]

def search_products_with_handoff_func(query: str, lang: str = "en") -> str:
    """Search for multiple products matching the query using products_export.json via ProductLoader, always send all (up to 10) in interactive list, localize as needed."""
    import json
    log_agent("HANDOFF", "search_products", query=query)
    try:
        # Patch: If query is generic, return top 10 products
        generic_queries = [
            "all", "everything", "show all", "show me all", "display all", "see all", "give me all", "options", "more"
        ]
        q_lower = query.strip().lower()
        if q_lower in generic_queries or any(gq in q_lower for gq in generic_queries):
            products = []
            if hasattr(product_loader, 'df') and product_loader.df is not None:
                handles = product_loader.df['Handle'].unique().tolist()
                products = product_loader.get_products_paginated(handles, lang=lang, page=1, page_size=10)
            # Only the first 10 products, in a section titled 'Products'
            section_items = []
            used_payloads = set()
            for idx, p in enumerate(products):
                pid = safe_field(p.get("id"), 200, f"item{idx}")
                title = safe_field(p.get("name"), 24, f"Item {idx+1}")
                payload = pid
                if payload in used_payloads:
                    payload = f"{payload}_{idx}"
                used_payloads.add(payload)
                section_items.append({
                    "id": pid,
                    "payload": payload,
                    "title": title
                })
            sections = []
            if section_items:
                sections.append({
                    "title": safe_field(get_translation("product_list_title", lang), 24, "Products"),
                    "items": section_items
                })
            payload = {
                "whatsapp_type": "interactive_list",
                "interactiveList": {
                    "body": {"text": get_translation("found_products", lang, count=len(products))},
                    "list": {
                        "title": safe_field(get_translation("product_list_title", lang), 24, "Products"),
                        "header": {"text": safe_field(get_translation("product_list_title", lang), 24, "Products")},
                        "sections": sections
                    }
                }
            }
            print("INTERACTIVE LIST PAYLOAD:")
            print(json.dumps(payload, indent=2))
            log_agent("HANDOFF", "multiple_products_result", query=query, count=len(products))
            return json.dumps(payload)
        # --- original logic below ---
        products = product_loader.search(query, lang=lang, max_results=10)
        if products:
            if len(products) == 1:
                product = products[0]
                # Improved: Extract main name (e.g., 'SCIURUS 155' from 'SCIURUS 155 II')
                import re
                name = product.get("name", "")
                # Match main name (letters, numbers, spaces) before a variant suffix (Roman numerals or similar)
                match = re.match(r"^([A-Za-z0-9\- ]+?)(?:\s+[IVXLCDM]+)?$", name)
                base_name = match.group(1).strip() if match else name
                # Find up to 3 variant products (same main name, different variant)
                all_variants = [p for p in product_loader.search(base_name, lang=lang, max_results=10)
                                if p.get("id") != product.get("id") and p.get("name", "").startswith(base_name)]
                # Exclude exact name matches (only different variants)
                variants = [v for v in all_variants if v.get("name") != name][:3]
                variant_templates = []
                for v in variants:
                    image_url = v.get("image_url", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=400")
                    prod_name = v.get("name", "Product")
                    prod_url = v.get("url", "https://www.theleva.com/")
                    print(f"TEMPLATE VARIANT: name={prod_name}, image_url={image_url}, url={prod_url}")
                    variant_templates.append({
                        "whatsapp_type": "buttonTemplate",
                        "template_id": "zoko_upsell_product_01",
                        "template_args": [
                            image_url,
                            prod_name,
                            get_translation("order_product", lang, product=prod_name),
                            prod_url
                        ]
                    })
                image_url = product.get("image_url", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=400")
                prod_name = product.get("name", "Product")
                prod_url = product.get("url", "https://www.theleva.com/")
                print(f"TEMPLATE MAIN: name={prod_name}, image_url={image_url}, url={prod_url}")
                response = [{
                    "whatsapp_type": "buttonTemplate",
                    "template_id": "zoko_upsell_product_01",
                    "template_args": [
                        image_url,
                        prod_name,
                        get_translation("order_product", lang, product=prod_name),
                        prod_url
                    ]
                }] + variant_templates
                print("TEMPLATE PAYLOAD:")
                print(json.dumps(response[0], indent=2))
                return json.dumps(response[0]) if len(response) == 1 else json.dumps(response)
            else:
                # Only the first 6 products, regardless of category, in a section titled 'Products'
                section_items = []
                used_payloads = set()
                for idx, p in enumerate(products):
                    pid = safe_field(p.get("id"), 200, f"item{idx}")
                    title = safe_field(p.get("name"), 24, f"Item {idx+1}")
                    payload = pid
                    if payload in used_payloads:
                        payload = f"{payload}_{idx}"
                    used_payloads.add(payload)
                    section_items.append({
                        "id": pid,
                        "payload": payload,
                        "title": title
                    })
                sections = []
                if section_items:
                    sections.append({
                        "title": safe_field(get_translation("product_list_title", lang), 24, "Products"),
                        "items": section_items
                    })
                payload = {
                    "whatsapp_type": "interactive_list",
                    "interactiveList": {
                        "body": {"text": get_translation("found_products", lang, count=len(products))},
                        "list": {
                            "title": safe_field(get_translation("product_list_title", lang), 24, "Products"),
                            "header": {"text": safe_field(get_translation("product_list_title", lang), 24, "Products")},
                            "sections": sections
                        }
                    }
                }
                print("INTERACTIVE LIST PAYLOAD:")
                print(json.dumps(payload, indent=2))
                log_agent("HANDOFF", "multiple_products_result", query=query, count=len(products))
                return json.dumps(payload)
        log_agent("HANDOFF", "no_products_found", query=query)
        return json.dumps({
            "whatsapp_type": "text",
            "message": get_translation("no_products", lang)
        })
    except Exception as e:
        log_error("HANDOFF", str(e), query=query, function="search_products_with_handoff")
        return json.dumps({
            "whatsapp_type": "text",
            "message": get_translation("no_products", lang)
        })
@function_tool
def search_products_with_handoff(query: str, lang: str = "en") -> str:
    """Search for multiple products with handoff to database agent."""
    return search_products_with_handoff_func(query, lang)

def search_one_product_with_handoff_func(query: str, lang: str = "en") -> str:
    """Search for a single product matching the query using CSV loader, localize as needed."""
    logger.info(f"🔍 Searching one product with handoff: {query}")
    try:
        products = product_loader.search(query, lang=lang, max_results=1)
        if products:
            product = products[0]
            return json.dumps({
                "whatsapp_type": "buttonTemplate",
                "template_id": "zoko_upsell_product_01",
                "template_args": [
                    product.get("image_url", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=400"),
                    product.get("name", "Product"),
                    get_translation("order_product", lang, product=product.get("name", "Product")),
                    product.get("url", "https://www.theleva.com/")
                ]
            })
        return json.dumps({
            "whatsapp_type": "text",
            "message": get_translation("no_products", lang)
        })
    except Exception as e:
        logger.error(f"❌ Single product search failed: {str(e)}")
        return json.dumps({
            "whatsapp_type": "text",
            "message": get_translation("no_products", lang)
        })

@function_tool
def search_one_product_with_handoff(query: str, lang: str = "en") -> str:
    """Search for a single product with handoff to database agent."""
    return search_one_product_with_handoff_func(query, lang)

# def get_property_details_with_handoff_func(property_id: str, lang: str = "en") -> str:
#     """Get details for a specific product by ID and return using 'upsel_01' template. Localize all UI/system messages."""
#     logger.info(f"🔍 Fetching product details for ID: {property_id}")
#     try:
#         # Assuming search_database_func supports fetching by ID
#         result = search_database_func("get_by_id", property_id=property_id)
#         result_data = json.loads(result) if isinstance(result, str) else result
#         if result_data.get("products"):
#             product = result_data["products"][0]
#             return json.dumps({
#                 "whatsapp_type": "buttonTemplate",
#                 "template_id": "zoko_upsell_product_01",
#                 "template_args": [
#                     product.get("image_url", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=400"),
#                     product.get("title", get_translation("product_list_title", lang)),
#                     get_translation("order_product", lang, product=product.get("title", "House")),
#                     product.get("url", "https://www.theleva.com/")
#                 ]
#             })
#         return json.dumps({
#             "whatsapp_type": "text",
#             "message": get_translation("no_product_with_id", lang, id=property_id)
#         })
#     except Exception as e:
#         logger.error(f"❌ Product details fetch failed: {str(e)}")
#         return json.dumps({
#             "whatsapp_type": "text",
#             "message": get_translation("error_fetching_product_details", lang)
#         })

# @function_tool
# def get_property_details_with_handoff(property_id: str, lang: str = "en") -> str:
#     """Get product details with handoff to database agent."""
#     return get_property_details_with_handoff_func(property_id, lang)

# def browse_all_properties_with_handoff_func(limit: int = 20, lang: str = "en") -> str:
#     """Browse all available properties and return an interactive list. Localize all UI/system messages."""
#     logger.info(f"🔍 Browsing all properties (limit: {limit})")
#     try:
#         result = search_database_func("search", query="", limit=limit)
#         result_data = json.loads(result) if isinstance(result, str) else result
#         if result_data.get("products"):
#             products = result_data["products"]
#             sections = [
#                 {
#                     "title": get_translation("product_list_title", lang),
#                     "items": [
#                         {
#                             "id": p["id"],
#                             "payload": p["id"],
#                             "title": p["title"][:24],
#                             "description": (p.get("description") or p.get("body_html") or "")[:60]
#                         } for p in products[:limit] if p.get("id") and p.get("title")
#                     ]
#                 }
#             ]
#             return json.dumps({
#                 "whatsapp_type": "interactive_list",
#                 "interactiveList": {
#                     "body": {"text": get_translation("found_products", lang, count=len(products))},
#                     "list": {
#                         "title": get_translation("product_list_title", lang),
#                         "header": {"text": get_translation("product_list_title", lang)},
#                         "sections": sections
#                     }
#                 }
#             })
#         return json.dumps({
#             "whatsapp_type": "text",
#             "message": get_translation("no_products", lang)
#         })
#     except Exception as e:
#         logger.error(f"❌ Browse all properties failed: {str(e)}")
#         return json.dumps({
#             "whatsapp_type": "text",
#             "message": get_translation("error_browsing_products", lang)
#         })

# @function_tool
# def browse_all_properties_with_handoff(limit: int = 20, lang: str = "en") -> str:
#     """Browse all properties with handoff to database agent."""
#     return browse_all_properties_with_handoff_func(limit, lang)
