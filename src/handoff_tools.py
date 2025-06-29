import json
import asyncio
from typing import Dict, Optional
from agents import function_tool
from src.logger import get_logger
from src.db_agent import handle_database_request

logger = get_logger("handoff_tools")

# Regular function for direct calls (used in tests)
def handoff_to_database_agent_func(request: str, reason: str = "") -> str:
    """
    Regular function version of handoff_to_database_agent for direct calls.
    
    Args:
        request: The database operation request to be handled
        reason: Reason for the handoff (e.g., "complex search", "database error")
    
    Returns:
        JSON string with database agent response and WhatsApp template data
    """
    logger.info(f"🔄 Handing off to database agent: {request[:100]}... (Reason: {reason})")
    
    try:
        # Use direct database search instead of agent to avoid event loop issues
        from src.tools import search_database_func
        
        # Extract the search query from the request
        if "Search for properties matching:" in request:
            query = request.replace("Search for properties matching:", "").strip()
            result = search_database_func("search", query=query)
        elif "Get all available properties" in request:
            result = search_database_func("browse_all")
        elif "Get details for property ID:" in request:
            property_id = request.replace("Get details for property ID:", "").strip()
            result = search_database_func("get_details", property_id=property_id)
        else:
            # Fallback to search
            result = search_database_func("search", query=request)
        
        # Parse the result and add handoff metadata
        if isinstance(result, str):
            try:
                result_data = json.loads(result)
            except json.JSONDecodeError:
                result_data = {"message": result, "whatsapp_type": "text"}
        else:
            result_data = result
        
        result_data["handoff_info"] = {
            "from_agent": "main_agent",
            "to_agent": "database_agent",
            "reason": reason,
            "timestamp": "2025-01-28T00:00:00Z"
        }
        
        logger.info(f"✅ Database agent handoff completed successfully")
        return json.dumps(result_data)
        
    except Exception as e:
        logger.error(f"❌ Database agent handoff failed: {str(e)}")
        return json.dumps({
            "success": False,
            "message": "Sorry, I'm having trouble with the database operation right now.",
            "whatsapp_type": "text",
            "handoff_required": True,
            "handoff_reason": f"Database agent handoff failed: {str(e)}",
            "handoff_info": {
                "from_agent": "main_agent",
                "to_agent": "database_agent",
                "reason": reason,
                "status": "failed",
                "error": str(e)
            }
        })

@function_tool
def handoff_to_database_agent(request: str, reason: str = "") -> str:
    """
    Handoff to the specialized database agent for database operations.
    
    Args:
        request: The database operation request to be handled
        reason: Reason for the handoff (e.g., "complex search", "database error")
    
    Returns:
        JSON string with database agent response and WhatsApp template data
    """
    return handoff_to_database_agent_func(request, reason)

# Regular function for direct calls (used in tests)
def search_products_with_handoff_func(query: str) -> str:
    """
    Regular function version of search_products_with_handoff for direct calls.
    
    Args:
        query: Search terms for product search
    
    Returns:
        JSON string with search results from database agent, including template info
    """
    logger.info(f"🔍 Searching products with handoff: {query}")
    
    try:
        # Use direct database search
        from src.tools import search_database_func
        from src.zoko_utils import zoko_utils
        
        result = search_database_func("search", query=query)
        
        # Parse the result
        if isinstance(result, str):
            try:
                result_data = json.loads(result)
            except json.JSONDecodeError:
                result_data = {"message": result, "whatsapp_type": "text"}
        else:
            result_data = result
        
        # Always return structured product data with template info
        if "products" in result_data and result_data["products"]:
            products = result_data["products"]
            count = len(products)
            product_cards = []
            for product in products:
                # AI chooses the template and args for each product
                template_suggestions = zoko_utils.get_template_suggestions("buttonTemplate")
                # For demo, pick the first active template with 4 variables (e.g., zoko_upsell_product_01)
                template = next((tpl for tpl in template_suggestions if tpl['variables'] == 4), template_suggestions[0])
                template_id = template['templateId']
                template_args = [
                    product.get("image_url", "https://via.placeholder.com/400x300?text=Product"),
                    product.get("title", "Product"),
                    f"PROD-{product.get('id', 'unknown')}",
                    f"view_details_{product.get('id', 'unknown')}"
                ]
                product_cards.append({
                    "template_id": template_id,
                    "template_args": template_args,
                    "product": product
                })
            result_data["product_cards"] = product_cards
            result_data["whatsapp_type"] = "buttonTemplate"
            result_data["message"] = f"Found {count} products matching '{query}'."
        else:
            result_data["message"] = f"Sorry, I couldn't find any products matching '{query}'. Try searching for something else!"
            result_data["whatsapp_type"] = "text"
        
        result_data["handoff_info"] = {
            "from_agent": "main_agent",
            "to_agent": "database_agent",
            "reason": "product search",
            "timestamp": "2025-01-28T00:00:00Z"
        }
        
        logger.info(f"✅ Product search completed successfully")
        return json.dumps(result_data)
        
    except Exception as e:
        logger.error(f"❌ Product search failed: {str(e)}")
        return json.dumps({
            "success": False,
            "message": "Sorry, I'm having trouble searching for products right now.",
            "whatsapp_type": "text",
            "handoff_required": True,
            "handoff_reason": f"Product search failed: {str(e)}",
            "handoff_info": {
                "from_agent": "main_agent",
                "to_agent": "database_agent",
                "reason": "product search",
                "status": "failed",
                "error": str(e)
            }
        })

@function_tool
def search_products_with_handoff(query: str) -> str:
    """
    Search products with automatic handoff to database agent.
    
    Args:
        query: Search terms for product search
    
    Returns:
        JSON string with search results from database agent, including template info
    """
    return search_products_with_handoff_func(query)

# Regular function for direct calls (used in tests)
def browse_all_properties_with_handoff_func(limit: int = 20) -> str:
    """
    Regular function version of browse_all_properties_with_handoff for direct calls.
    
    Args:
        limit: Maximum number of properties to return
    
    Returns:
        JSON string with all properties from database agent
    """
    logger.info(f"📋 Browsing all properties with handoff (limit: {limit})")
    return handoff_to_database_agent_func(f"Get all available properties (limit: {limit})", "property browsing")

@function_tool
def browse_all_properties_with_handoff(limit: int = 20) -> str:
    """
    Browse all properties with automatic handoff to database agent.
    
    Args:
        limit: Maximum number of properties to return
    
    Returns:
        JSON string with all properties from database agent
    """
    return browse_all_properties_with_handoff_func(limit)

# Regular function for direct calls (used in tests)
def get_property_details_with_handoff_func(property_id: str) -> str:
    """
    Regular function version of get_property_details_with_handoff for direct calls.
    
    Args:
        property_id: The property ID to get details for
    
    Returns:
        JSON string with property details from database agent
    """
    logger.info(f"📄 Getting property details with handoff: {property_id}")
    return handoff_to_database_agent_func(f"Get details for property ID: {property_id}", "property details")

@function_tool
def get_property_details_with_handoff(property_id: str) -> str:
    """
    Get property details with automatic handoff to database agent.
    
    Args:
        property_id: The property ID to get details for
    
    Returns:
        JSON string with property details from database agent
    """
    return get_property_details_with_handoff_func(property_id)

# Regular function for direct calls (used in tests)
def complex_database_query_func(query: str, operation_type: str = "search") -> str:
    """
    Regular function version of complex_database_query for direct calls.
    
    Args:
        query: The complex database query
        operation_type: Type of operation ("search", "browse", "details", "custom")
    
    Returns:
        JSON string with database agent response
    """
    logger.info(f"🔧 Complex database query with handoff: {operation_type} - {query}")
    
    handoff_reason = f"complex {operation_type} operation"
    return handoff_to_database_agent_func(f"Perform {operation_type} operation: {query}", handoff_reason)

@function_tool
def complex_database_query(query: str, operation_type: str = "search") -> str:
    """
    Handle complex database queries with handoff to database agent.
    
    Args:
        query: The complex database query
        operation_type: Type of operation ("search", "browse", "details", "custom")
    
    Returns:
        JSON string with database agent response
    """
    return complex_database_query_func(query, operation_type) 

# Regular function for direct calls (used in tests)
def search_one_product_with_handoff_func(query: str) -> str:
    """
    Regular function version of search_one_product_with_handoff for direct calls.
    Args:
        query: Search terms for product search
    Returns:
        JSON string with only ONE product result and template info
    """
    logger.info(f"🔍 Searching for ONE product with handoff: {query}")
    try:
        from src.tools import search_database_func
        from src.zoko_utils import zoko_utils
        result = search_database_func("search", query=query, limit=1)
        if isinstance(result, str):
            try:
                result_data = json.loads(result)
            except json.JSONDecodeError:
                result_data = {"message": result, "whatsapp_type": "text"}
        else:
            result_data = result
        if "products" in result_data and result_data["products"]:
            product = result_data["products"][0]
            template_suggestions = zoko_utils.get_template_suggestions("buttonTemplate")
            template = next((tpl for tpl in template_suggestions if tpl['variables'] == 4), template_suggestions[0])
            template_id = template['templateId']
            template_args = [
                product.get("image_url", "https://via.placeholder.com/400x300?text=Product"),
                product.get("title", "Product"),
                f"PROD-{product.get('id', 'unknown')}",
                f"view_details_{product.get('id', 'unknown')}"
            ]
            result_data["product_card"] = {
                "template_id": template_id,
                "template_args": template_args,
                "product": product
            }
            result_data["whatsapp_type"] = "buttonTemplate"
            result_data["message"] = f"Here's one product matching '{query}'."
            logger.info(f"🖼️ Using image URL for template: {product.get('image_url')}")
        else:
            result_data["message"] = f"Sorry, I couldn't find any products matching '{query}'. Try searching for something else!"
            result_data["whatsapp_type"] = "text"
        result_data["handoff_info"] = {
            "from_agent": "main_agent",
            "to_agent": "database_agent",
            "reason": "one product search",
            "timestamp": "2025-01-28T00:00:00Z"
        }
        logger.info(f"✅ One product search completed successfully")
        return json.dumps(result_data)
    except Exception as e:
        logger.error(f"❌ One product search failed: {str(e)}")
        return json.dumps({
            "success": False,
            "message": "Sorry, I'm having trouble searching for products right now.",
            "whatsapp_type": "text",
            "handoff_required": True,
            "handoff_reason": f"One product search failed: {str(e)}",
            "handoff_info": {
                "from_agent": "main_agent",
                "to_agent": "database_agent",
                "reason": "one product search",
                "status": "failed",
                "error": str(e)
            }
        })

@function_tool
def search_one_product_with_handoff(query: str) -> str:
    """
    Search for one product with automatic handoff to database agent.
    Args:
        query: Search terms for product search
    Returns:
        JSON string with only ONE product result and template info
    """
    return search_one_product_with_handoff_func(query)

# Product details

def get_product_details_with_handoff_func(product_id: str) -> str:
    """
    Regular function version of get_product_details_with_handoff for direct calls.
    Args:
        product_id: The product ID to get details for
    Returns:
        JSON string with full product details and template info
    """
    logger.info(f"📄 Getting product details with handoff: {product_id}")
    try:
        from src.tools import search_database_func
        from src.zoko_utils import zoko_utils
        clean_id = product_id
        if product_id.startswith("view_product_"):
            clean_id = product_id.replace("view_product_", "")
        elif product_id == "view_details_payload":
            clean_id = product_id.replace("view_details_", "")
        result = search_database_func("get_details", property_id=clean_id)
        if isinstance(result, str):
            try:
                result_data = json.loads(result)
            except json.JSONDecodeError:
                result_data = {"message": result, "whatsapp_type": "text"}
        else:
            result_data = result
        if "product" in result_data and result_data["product"]:
            product = result_data["product"]
            template_suggestions = zoko_utils.get_template_suggestions("buttonTemplate")
            template = next((tpl for tpl in template_suggestions if tpl['variables'] == 4), template_suggestions[0])
            template_id = template['templateId']
            template_args = [
                product.get("image_url", "https://via.placeholder.com/400x300?text=Product"),
                product.get("title", "Product"),
                f"PROD-{product.get('id', 'unknown')}",
                f"buy_now_{product.get('id', 'unknown')}"
            ]
            result_data["product_card"] = {
                "template_id": template_id,
                "template_args": template_args,
                "product": product
            }
            result_data["whatsapp_type"] = "buttonTemplate"
            result_data["message"] = f"Here are the details for the selected product."
            logger.info(f"🖼️ Using image URL for template: {product.get('image_url')}")
        else:
            result_data["message"] = f"Sorry, I couldn't find details for this product."
            result_data["whatsapp_type"] = "text"
        result_data["handoff_info"] = {
            "from_agent": "main_agent",
            "to_agent": "database_agent",
            "reason": "product details",
            "timestamp": "2025-01-28T00:00:00Z"
        }
        logger.info(f"✅ Product details fetched successfully")
        return json.dumps(result_data)
    except Exception as e:
        logger.error(f"❌ Product details failed: {str(e)}")
        return json.dumps({
            "success": False,
            "message": "Sorry, I'm having trouble fetching product details right now.",
            "whatsapp_type": "text",
            "handoff_required": True,
            "handoff_reason": f"Product details failed: {str(e)}",
            "handoff_info": {
                "from_agent": "main_agent",
                "to_agent": "database_agent",
                "reason": "product details",
                "status": "failed",
                "error": str(e)
            }
        })

@function_tool
def get_product_details_with_handoff(product_id: str) -> str:
    """
    Get product details with automatic handoff to database agent.
    Args:
        product_id: The product ID to get details for
    Returns:
        JSON string with full product details and template info
    """
    return get_product_details_with_handoff_func(product_id) 