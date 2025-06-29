import os
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from agents import Agent
from src.logger import get_logger
from src.tools import search_database

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = get_logger("db_agent")

# Database agent specialized in database operations
# Following official OpenAI Agents SDK patterns
db_agent = Agent(
    name="database_agent",
    instructions="""
 You are a specialized database agent for product management and search operations.

## 🎯 CORE MISSION
Handle all database-related operations including product searches, browsing, and detailed information retrieval.

## 🧠 EXPERTISE AREAS
- Product search and filtering
- Database query optimization
- Product details and metadata
- Search result formatting
- Database error handling

## 🛠️ TOOL USAGE RULES

### search_database(action, query, product_id, limit)
- action: "search", "browse_all", or "get_details"
- query: Search terms for product search
- product_id: Specific product ID for details
- limit: Maximum results (default 10)

### Usage Examples:
- search_database("search", query="LYNX Product")
- search_database("search", query="iPhone 15")
- search_database("browse_all", limit=20)
- search_database("get_details", product_id="12345")

## 📊 DATABASE OPERATIONS

### Product Search
- Handle complex search queries
- Optimize search terms for better results
- Provide search suggestions when no results found
- Format results for WhatsApp templates

### Product Browsing
- Retrieve all available products
- Apply intelligent filtering and sorting
- Limit results appropriately
- Create interactive lists for multiple products

### Product Details
- Fetch detailed product information
- Handle product ID validation
- Provide comprehensive product data
- Format for rich WhatsApp templates

## 🚨 ERROR HANDLING
- Database connection issues
- Invalid product IDs
- Search query optimization
- Result formatting errors

## 📱 WHATSAPP INTEGRATION
- Format results for WhatsApp templates
- Create button templates for single products
- Generate interactive lists for multiple products
- Handle template argument formatting

## 🎯 RESPONSE PATTERNS

### Successful Search
→ Return structured JSON with:
- success: true
- products: array of products
- template: WhatsApp template data
- whatsapp_type: template type

### No Results
→ Return structured JSON with:
- success: true
- message: helpful suggestions
- suggestions: alternative search terms
- handoff_required: false

### Database Error
→ Return structured JSON with:
- success: false
- message: error description
- handoff_required: true
- handoff_reason: technical issue description

## 💬 CONVERSATION FLOW
1. **Analyze the request** - understand what database operation is needed
2. **Execute the operation** - use the appropriate search_database action
3. **Format the results** - structure data for WhatsApp templates
4. **Handle errors gracefully** - provide helpful error messages
5. **Suggest alternatives** - when no results found

## 🚫 WHAT NOT TO DO
- Don't hallucinate product data
- Don't ignore database errors
- Don't return unformatted data
- Don't exceed reasonable result limits
- Don't ignore handoff signals

## ✅ SUCCESS METRICS
- Fast and accurate database queries
- Proper error handling and recovery
- Well-formatted WhatsApp templates
- Helpful search suggestions
- Smooth handoff coordination

Be efficient, accurate, and always provide structured, actionable database results.
""",
    model="o3-mini",
    tools=[search_database]
)

async def handle_database_request(request: str, chat_id: str = None) -> Dict:
    """
    Handle database operations through the specialized database agent.
    
    Args:
        request: The database operation request
        chat_id: Chat ID for context
    
    Returns:
        Dict with database results and WhatsApp template data
    """
    logger.info(f"🗄️ Database agent processing: {request[:100]}...")
    
    try:
        from agents import Runner
        
        # Run the database agent
        result = await Runner.run(db_agent, request)
        
        # Parse the response
        try:
            response_data = json.loads(result.final_output)
            if isinstance(response_data, dict):
                logger.info(f"✅ Database agent response generated successfully")
                return response_data
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Fallback to plain text if not JSON
        return {
            "message": result.final_output,
            "whatsapp_type": "text",
            "handoff_required": False
        }
        
    except Exception as e:
        logger.error(f"❌ Database agent error: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": "Sorry, I'm having trouble accessing the database right now.",
            "whatsapp_type": "text",
            "handoff_required": True,
            "handoff_reason": "Database agent error - technical assistance needed"
        }

# Utility functions for direct database access
def search_properties_via_agent(query: str) -> Dict:
    """Search properties using the database agent."""
    try:
        # Use direct database search instead of agent to avoid event loop issues
        from src.tools import search_database_func
        result = search_database_func("search", query=query)
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        logger.error(f"Database agent search failed: {e}")
        return {"success": False, "message": "Search failed", "products": []}

def get_all_properties_via_agent() -> Dict:
    """Get all properties using the database agent."""
    try:
        # Use direct database search instead of agent to avoid event loop issues
        from src.tools import search_database_func
        result = search_database_func("browse_all")
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        logger.error(f"Database agent browse failed: {e}")
        return {"success": False, "message": "Failed to get properties", "products": []}

def get_property_details_via_agent(property_id: str) -> Dict:
    """Get property details using the database agent."""
    try:
        # Use direct database search instead of agent to avoid event loop issues
        from src.tools import search_database_func
        result = search_database_func("get_details", property_id=property_id)
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        logger.error(f"Database agent details failed: {e}")
        return {"success": False, "message": "Failed to get property details", "product": None} 