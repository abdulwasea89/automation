import json
from typing import Dict, List
from agents import function_tool
from src.logger import get_logger

logger = get_logger("handoff_tools")

def search_products_with_handoff_func(query: str) -> str:
    """Search for multiple products matching the query and return an interactive list."""
    logger.info(f"🔍 Searching products with handoff: {query}")
    try:
        from src.tools import search_database_func
        result = search_database_func("search", query=query, limit=10)
        result_data = json.loads(result) if isinstance(result, str) else result
        if result_data.get("products"):
            products = result_data["products"]
            if len(products) == 1:
                product = products[0]
                return json.dumps({
                    "whatsapp_type": "buttonTemplate",
                    "template_id": "upsel_01",
                    "template_args": [
                        product.get("image_url", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=400"),
                        product.get("title", "House"),
                        f"Order {product.get('title', 'House')}",
                        product.get("url", "https://www.theleva.com/")
                    ]
                })
            sections = [
                {
                    "title": "Properties",
                    "items": [
                        {
                            "id": p["id"],
                            "payload": p["id"],
                            "title": p["title"][:24],
                            "description": p["description"][:60]
                        } for p in products[:10]
                    ]
                }
            ]
            return json.dumps({
                "whatsapp_type": "interactive_list",
                "interactiveList": {
                    "body": {"text": f"Found {len(products)} products matching your query."},
                    "list": {
                        "title": "LEVA Houses",
                        "header": {"text": "LEVA Houses"},
                        "sections": sections
                    }
                }
            })
        return json.dumps({
            "whatsapp_type": "text",
            "message": "Sorry, I couldn't find any products matching your query."
        })
    except Exception as e:
        logger.error(f"❌ Product search failed: {str(e)}")
        return json.dumps({
            "whatsapp_type": "text",
            "message": "Sorry, there was an error searching for products."
        })

@function_tool
def search_products_with_handoff(query: str) -> str:
    """Search for multiple products with handoff to database agent."""
    return search_products_with_handoff_func(query)

def search_one_product_with_handoff_func(query: str) -> str:
    """Search for a single product matching the query and return using 'upsel_01' template."""
    logger.info(f"🔍 Searching one product with handoff: {query}")
    try:
        from src.tools import search_database_func
        result = search_database_func("search", query=query, limit=1)
        result_data = json.loads(result) if isinstance(result, str) else result
        if result_data.get("products"):
            product = result_data["products"][0]
            return json.dumps({
                "whatsapp_type": "buttonTemplate",
                "template_id": "upsel_01",
                "template_args": [
                    product.get("image_url", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=400"),
                    product.get("title", "House"),
                    f"Order {product.get('title', 'House')}",
                    product.get("url", "https://www.theleva.com/")
                ]
            })
        return json.dumps({
            "whatsapp_type": "text",
            "message": "Sorry, I couldn't find a product matching your query."
        })
    except Exception as e:
        logger.error(f"❌ Single product search failed: {str(e)}")
        return json.dumps({
            "whatsapp_type": "text",
            "message": "Sorry, there was an error searching for the product."
        })

@function_tool
def search_one_product_with_handoff(query: str) -> str:
    """Search for a single product with handoff to database agent."""
    return search_one_product_with_handoff_func(query)

def get_property_details_with_handoff_func(property_id: str) -> str:
    """Get details for a specific product by ID and return using 'upsel_01' template."""
    logger.info(f"🔍 Fetching product details for ID: {property_id}")
    try:
        from src.tools import search_database_func
        # Assuming search_database_func supports fetching by ID
        result = search_database_func("get_by_id", property_id=property_id)
        result_data = json.loads(result) if isinstance(result, str) else result
        if result_data.get("products"):
            product = result_data["products"][0]
            return json.dumps({
                "whatsapp_type": "buttonTemplate",
                "template_id": "upsel_01",
                "template_args": [
                    product.get("image_url", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=400"),
                    product.get("title", "House"),
                    f"Order {product.get('title', 'House')}",
                    product.get("url", "https://www.theleva.com/")
                ]
            })
        return json.dumps({
            "whatsapp_type": "text",
            "message": f"Sorry, no product found with ID {property_id}."
        })
    except Exception as e:
        logger.error(f"❌ Product details fetch failed: {str(e)}")
        return json.dumps({
            "whatsapp_type": "text",
            "message": "Sorry, there was an error fetching the product details."
        })

@function_tool
def get_property_details_with_handoff(property_id: str) -> str:
    """Get product details with handoff to database agent."""
    return get_property_details_with_handoff_func(property_id)

def browse_all_properties_with_handoff_func(limit: int = 20) -> str:
    """Browse all available properties and return an interactive list."""
    logger.info(f"🔍 Browsing all properties (limit: {limit})")
    try:
        from src.tools import search_database_func
        result = search_database_func("search", query="", limit=limit)
        result_data = json.loads(result) if isinstance(result, str) else result
        if result_data.get("products"):
            products = result_data["products"]
            sections = [
                {
                    "title": "Properties",
                    "items": [
                        {
                            "id": p["id"],
                            "payload": p["id"],
                            "title": p["title"][:24],
                            "description": p["description"][:60]
                        } for p in products[:limit]
                    ]
                }
            ]
            return json.dumps({
                "whatsapp_type": "interactive_list",
                "interactiveList": {
                    "body": {"text": f"Found {len(products)} products available."},
                    "list": {
                        "title": "LEVA Houses",
                        "header": {"text": "LEVA Houses"},
                        "sections": sections
                    }
                }
            })
        return json.dumps({
            "whatsapp_type": "text",
            "message": "Sorry, no products are available at the moment."
        })
    except Exception as e:
        logger.error(f"❌ Browse all properties failed: {str(e)}")
        return json.dumps({
            "whatsapp_type": "text",
            "message": "Sorry, there was an error browsing products."
        })

@function_tool
def browse_all_properties_with_handoff(limit: int = 20) -> str:
    """Browse all properties with handoff to database agent."""
    return browse_all_properties_with_handoff_func(limit)