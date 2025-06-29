import os
import re
import json
import logging
import time
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv
from agents import Runner, Agent, function_tool
from agents.extensions.handoff_prompt import prompt_with_handoff_instructions
from agents.tracing import trace
from agents import MaxTurnsExceeded
from src.logger import get_logger
from src.db_agent import db_agent
from src.handoff_tools import (
    handoff_to_database_agent,
    search_products_with_handoff,
    browse_all_properties_with_handoff,
    get_property_details_with_handoff,
    search_one_product_with_handoff,
    get_product_details_with_handoff,
    complex_database_query
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = get_logger("openai_agent")

# Rate limiting for agent calls
class AgentRateLimiter:
    def __init__(self, max_calls_per_minute=100):  # Much higher limit
        self.max_calls = max_calls_per_minute
        self.calls = []
    
    def can_make_call(self) -> bool:
        """Check if we can make another call within rate limits."""
        now = time.time()
        # Remove calls older than 1 second (very short)
        self.calls = [call_time for call_time in self.calls if now - call_time < 1]
        
        if len(self.calls) < self.max_calls:
            self.calls.append(now)
            return True
        return False
    
    def get_wait_time(self) -> int:
        """Get how many seconds to wait before next call."""
        return 0  # No waiting time

# Global rate limiter
rate_limiter = AgentRateLimiter()

# Enhanced agent with planning, memory, and handoff capabilities
# Following official OpenAI Agents SDK patterns
agent = Agent(
    name="whatsapp_product_assistant",
    instructions=prompt_with_handoff_instructions("""
You are a WhatsApp product assistant. Your job is to analyze user messages and provide appropriate responses.

## 🧠 INTENT ANALYSIS RULES

### STEP 1: ANALYZE THE USER'S INTENT
First, determine what type of question/request the user is making:
For example:
**PRODUCT REQUESTS** (Search immediately):
- "I need lynx product"
- "Show me iPhone 15"
- "Find products with pool"
- "Search for laptops"
- "I want to buy a car"
- "Looking for apartments"
- Any mention of specific products, brands, categories
for example:
**SPECIAL CASES:**
- "Give me one product" → Return only ONE product with template
- "Only one product" → Return only ONE product with template
- "Just one" → Return only ONE product with template
- "view_product_123" → Get full details for product ID 123
- "view_details_payload" → Get full details for the product

**GENERAL QUESTIONS** (Answer directly):
- "Hello", "Hi", "How are you"
- "What can you do?"
- "Thank you"
- "Goodbye"
- General greetings and non-product questions

### STEP 2: RESPONSE STRATEGY

**FOR PRODUCT REQUESTS:**
1. IMMEDIATELY use search_products_with_handoff(query)
2. Extract the product name/brand from user message
3. Search for that specific product
4. **CRITICAL: Return the EXACT JSON response from the search tool, including template_id, template_args, and all product info**
5. Do NOT convert to plain text - preserve the structured data

**FOR "ONE PRODUCT" REQUESTS:**
1. Use search_products_with_handoff(query)
2. Take only the FIRST product from results
3. Return single product template response

**FOR PRODUCT SELECTION:**
1. Extract product ID from "view_product_123" or "view_details_payload"
2. Use get_product_details_with_handoff(product_id)
3. Return full product details with rich template

**FOR GENERAL QUESTIONS:**
1. Answer directly and helpfully
2. No database search needed
3. Keep response conversational

## 🛠️ TOOL USAGE RULES

### search_products_with_handoff(query)
- Use for ANY product mention
- Extract the product name from user message
- Examples:
  - User: "I need lynx" → search_products_with_handoff("lynx")
  - User: "Show me iPhone" → search_products_with_handoff("iPhone")
  - User: "Find laptops" → search_products_with_handoff("laptops")
- **IMPORTANT: Return the tool's JSON response directly, including template info**

### search_one_product_with_handoff(query)
- Use when user asks for "one product" or "only one"
- Examples:
  - User: "Give me one lynx product" → search_one_product_with_handoff("lynx")
  - User: "Only one product" → search_one_product_with_handoff("product")
  - User: "Just one" → search_one_product_with_handoff("product")
- Returns only ONE product with template

### get_product_details_with_handoff(product_id)
- Use when user selects a product
- Extract ID from "view_product_123" → get_product_details_with_handoff("view_product_123")
- Extract ID from "view_details_payload" → get_product_details_with_handoff("view_details_payload")
- Returns full product details with rich template

### browse_all_properties_with_handoff(limit)
- Use when user wants to see all products
- User: "Show me everything" or "Browse all"

### get_property_details_with_handoff(property_id)
- Use when user wants details of specific product ID
- Direct ID lookup

## 📱 WHATSAPP TEMPLATE RESPONSES

**For Product Results:**
- Single product → Use button template with full details (AI chooses template)
- Multiple products → Use interactive list template or multiple product cards (AI chooses template)
- No results → Suggest alternatives

**For Product Selection:**
- Full product details → Use rich template with image, description, price, buttons (AI chooses template)

**For General Questions:**
- Simple text response
- Helpful and conversational

## 🚨 CRITICAL RULES

1. **ALWAYS search when user mentions ANY product/brand/category**
2. **NEVER ask for clarification on product names** - just search!
3. **Use templates for product responses (AI chooses template from available Zoko templates)**
4. **Answer general questions directly**
5. **Be helpful and conversational**
6. **CRITICAL: Return structured JSON for products, not plain text**
7. **For "one product" requests: Return only the first product**
8. **For product selection: Return full details with rich template**

## 📋 EXAMPLES

**User: "I need lynx product"**
→ search_products_with_handoff("lynx")
→ Return the EXACT JSON response with products and template data (AI chooses template)

**User: "Give me one lynx product"**
→ search_one_product_with_handoff("lynx")
→ Return single product template (AI chooses template)

**User: "view_product_123"**
→ get_product_details_with_handoff("view_product_123")
→ Return full product details with rich template (AI chooses template)

**User: "view_details_payload"**
→ get_product_details_with_handoff("view_details_payload")
→ Return full product details with rich template (AI chooses template)

**User: "Hello"**
→ "Hello! I'm here to help you find products. What are you looking for today?"

**User: "Show me iPhone 15"**
→ search_products_with_handoff("iPhone 15")
→ Return the EXACT JSON response with products and template data (AI chooses template)

**User: "Thank you"**
→ "You're welcome! Let me know if you need anything else."

## 🚫 WHAT NOT TO DO
- Don't ask for clarification on product names
- Don't ignore product mentions
- Don't give generic responses to product requests
- Don't search for general questions
- **DON'T convert product search results to plain text**
- **DON'T show lists when user asks for "one product"**

When in doubt about product intent, SEARCH!
"""),
    model="o3-mini",
    tools=[
        search_products_with_handoff,
        search_one_product_with_handoff,
        get_product_details_with_handoff,
        browse_all_properties_with_handoff,
        get_property_details_with_handoff
    ]
)

class ConversationMemory:
    """Enhanced conversation memory management."""
    
    def __init__(self):
        self.collection = "conversation_memory"
    
    def save_message(self, chat_id: str, role: str, message: str) -> bool:
        """Save a message to conversation memory."""
        try:
            from src.deps import db
            if db is None:
                logger.warning("Database not available for memory storage")
                return False
            
            memory_ref = db.collection(self.collection).document(chat_id)
            doc = memory_ref.get()
            
            if doc.exists:
                memory_data = doc.to_dict()
                messages = memory_data.get("messages", [])
            else:
                messages = []
            
            new_message = {
                "role": role,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            messages.append(new_message)
            
            # Keep only last 50 messages
            if len(messages) > 50:
                messages = messages[-50:]
            
            memory_ref.set({
                "chat_id": chat_id,
                "messages": messages,
                "last_updated": datetime.now().isoformat(),
                "message_count": len(messages)
            })
            
            logger.info(f"💾 Saved {role} message to memory for {chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save conversation memory: {e}")
            return False
    
    def get_memory(self, chat_id: str) -> List[Dict]:
        """Get conversation memory for context."""
        try:
            from src.deps import db
            if db is None:
                logger.warning("Database not available for memory retrieval")
                return []
            
            memory_ref = db.collection(self.collection).document(chat_id)
            doc = memory_ref.get()
            
            if doc.exists:
                memory_data = doc.to_dict()
                messages = memory_data.get("messages", [])
                logger.info(f"📖 Retrieved {len(messages)} messages from memory for {chat_id}")
                return messages
            else:
                logger.info(f"📖 No memory found for {chat_id}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get conversation memory: {e}")
            return []
    
    def build_context(self, chat_id: str, current_message: str) -> str:
        """Build conversation context from memory."""
        try:
            memory_messages = self.get_memory(chat_id)
            if not memory_messages:
                return current_message
            
            # Only use last 1 message to save tokens
            recent_messages = memory_messages[-1:]  # Reduced from 2 to 1
            context_parts = []
            
            for msg in recent_messages:
                role = msg.get("role", "unknown")
                content = msg.get("message", "")
                # Truncate content to save tokens
                if len(content) > 50:  # Reduced from 100 to 50
                    content = content[:50] + "..."
                
                if role == "user":
                    context_parts.append(f"U: {content}")
                elif role == "bot":
                    context_parts.append(f"A: {content}")
            
            context = "\n".join(context_parts)
            context += f"\nU: {current_message}"
            
            logger.info(f"🧠 Built context for {chat_id} with {len(recent_messages)} recent messages")
            return context
            
        except Exception as e:
            logger.error(f"Failed to build conversation context: {e}")
            return current_message

# Global memory instance
memory = ConversationMemory()

def parse_agent_response(response: str) -> Dict:
    """
    Parse agent response and extract structured data.
    Returns dict with message, template data, and WhatsApp type.
    """
    try:
        # Try to parse as JSON first
        data = json.loads(response)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, TypeError):
        pass
    
    # Fallback to plain text
    return {
        "message": response,
        "whatsapp_type": "text"
    }

async def chat_with_agent_enhanced(
    user_message: str, 
    user_lang: str = "en", 
    chat_id: str = None
) -> Dict:
    """
    Enhanced chat function with memory, planning, and handoff capabilities.
    
    Args:
        user_message: The user's message
        user_lang: User's language preference
        chat_id: Chat ID for memory context
    
    Returns:
        Dict with response data and WhatsApp template information
    """
    logger.info(f"🤖 Processing message: {user_message[:50]}...")  # Reduced log length
    
    try:
        # Check rate limiting
        if not rate_limiter.can_make_call():
            return {
                "message": "Please try again.",
                "whatsapp_type": "text",
                "handoff_required": False
            }
    
    # Build context with memory
        memory = ConversationMemory()
        context = memory.build_context(chat_id, user_message)
        
        # Simplified prompt to save tokens
        full_prompt = f"{context}\nA:"
        
        # Run agent with tracing (no max_iterations parameter)
        with trace(workflow_name="whatsapp_property_chat", group_id=os.getenv("ZOKO_CHANNEL_ID", "")):
            result = await Runner.run(agent, full_prompt)
        
        # Save messages to memory
        if chat_id:
            memory.save_message(chat_id, "user", user_message)
            memory.save_message(chat_id, "assistant", result.final_output)
        
        # Parse the response
        response_data = parse_agent_response(result.final_output)
        
        logger.info("✅ Agent response generated successfully")
        return response_data
        
    except Exception as e:
        logger.error(f"❌ Agent error: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": "I'm having trouble processing your request right now. Please try again.",
            "whatsapp_type": "text",
            "handoff_required": False
        }

# Backward compatibility
async def chat_with_agent(user_message: str, user_lang: str = "en", chat_id: str = None) -> Dict:
    """Backward compatibility function."""
    return await chat_with_agent_enhanced(user_message, user_lang, chat_id)

# Utility functions for direct database access
def search_products_direct(query: str) -> Dict:
    """Direct product search for API use."""
    try:
        import json
        result = search_products(query)
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        logger.error(f"Direct search failed: {e}")
        return {"success": False, "message": "Search failed", "products": []}

def get_all_products_direct() -> Dict:
    """Direct product retrieval for API use."""
    try:
        import json
        result = get_all_products()
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        logger.error(f"Direct product retrieval failed: {e}")
        return {"success": False, "message": "Failed to get products", "products": []}

def get_product_details_direct(product_id: str) -> Dict:
    """Direct product details for API use."""
    try:
        import json
        result = get_product_details(product_id)
        return json.loads(result) if isinstance(result, str) else result
    except Exception as e:
        logger.error(f"Direct product details failed: {e}")
        return {"success": False, "message": "Failed to get product details", "product": None} 