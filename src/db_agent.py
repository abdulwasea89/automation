import os
import json
import logging
from typing import Dict
from dotenv import load_dotenv
from agents import Agent, AsyncOpenAI, OpenAIChatCompletionsModel, RunConfig
from src.logger import get_logger
from src.tools import search_database

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = get_logger("db_agent")

# Gemini integration (commented out)
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# if not GEMINI_API_KEY:
#     raise ValueError("GEMINI_API_KEY is not set. Please ensure it is defined in your .env file.")
#
# gemini_client = AsyncOpenAI(
#     api_key=GEMINI_API_KEY,
#     base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
# )
#
# gemini_model = OpenAIChatCompletionsModel(
#     model="gemini-2.0-flash",
#     openai_client=gemini_client
# )
#
# gemini_config = RunConfig(
#     model=gemini_model,
#     model_provider=gemini_client,
#     tracing_disabled=True
# )

# o3-mini (OpenAI gpt-3.5-turbo) integration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Database agent
db_agent = Agent(
    name="database_agent",
    instructions="""
You are Leva's WhatsApp assistant. You handle product queries and general questions.

Respond in same language as user

CRITICAL RULES:
These are the examples below, user will ask any thing, so repond politely and respecfully and one things more is that donot answer irrelevant to leva  or distract from your work

Use the tools when the user query is about products and donot tool call when the users are telling a general tool call

The tool call is for only produts not general questions

1. For "What products do you have?" or "What do you offer?" - ALWAYS give this EXACT response:
   "I have pools, houses, family houses, clubhouse, spa, summerhouses, Luxury apartments, Single-family rental homes"

2. For specific product requests - ALWAYS use tools:
   - "Show me houses" → Call search_products_with_handoff("houses")
   - "I want a tiny house" → Call search_one_product_with_handoff("tiny house")
   - "Give me one house" → Call search_one_product_with_handoff("house")

3. For greetings and general questions - Give friendly responses:
   - "Hi", "Hello" → "Hello! 👋 How can I assist you with Leva's houses or services today?"

4. NEVER use tools for "What products do you have?" - always give the hardcoded list above.

RESPONSE FORMAT:
- For tool responses: Return the EXACT tool response - never reformat or summarize
- For direct responses: Return simple text without JSON formatting
- Never wrap in code blocks or JSON formatting

There are examples below 

EXAMPLES
User: "What products do you have?" → "I have pools, houses, family houses, clubhouse, spa, summerhouses, Luxury apartments, Single-family rental homes"
User: "What do you offer?" → "I have pools, houses, family houses, clubhouse, spa, summerhouses, Luxury apartments, Single-family rental homes"
User: "Show me houses" → Call search_products_with_handoff("houses")
User: "I want a tiny house" → Call search_one_product_with_handoff("tiny house")
User: "Hi" → "Hello! 👋 How can I assist you with Leva's houses or services today?"

CRITICAL: "What products do you have?" should NEVER call tools - always give the hardcoded list!
""",
model="o3-mini",
    tools=[search_database]
)

async def handle_database_request(request: str, chat_id: str = None) -> Dict:
    """Handle database operations through the specialized database agent."""
    logger.info(f"🗄️ Database agent processing: {request[:100]}...")
    try:
        from agents import Runner
        result = await Runner.run(db_agent, request)
        try:
            response_data = json.loads(result.final_output)
            if isinstance(response_data, dict):
                logger.info("✅ Database agent response generated successfully")
                return response_data
        except (json.JSONDecodeError, TypeError):
            pass
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