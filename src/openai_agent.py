import os
import orjson
import logging
import asyncio
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv
from agents import Runner, Agent, AsyncOpenAI, OpenAIChatCompletionsModel, RunConfig
from src.logger import get_logger
from src.handoff_tools import (
    search_products_with_handoff,
    search_one_product_with_handoff,
    get_property_details_with_handoff,
    browse_all_properties_with_handoff,
    search_products_with_handoff_func,
    search_one_product_with_handoff_func,
    get_property_details_with_handoff_func,
    browse_all_properties_with_handoff_func
)
import re

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = get_logger("openai_agent")

# Instantiate memory objects at the top to avoid "memory is not defined"
class ConversationMemory:
    """Short-term conversation memory management."""
    
    def __init__(self):
        self.collection = "conversation_memory"
    
    def save_message(self, chat_id: str, role: str, message: str) -> bool:
        """Save a message to short-term conversation memory."""
        try:
            from src.deps import db
            if db is None:
                logger.warning("Database not available for memory storage")
                return False
            memory_ref = db.collection(self.collection).document(chat_id)
            doc = memory_ref.get()
            messages = doc.to_dict().get("messages", []) if doc.exists else []
            messages.append({"role": role, "message": message, "timestamp": datetime.utcnow().isoformat()})
            memory_ref.set({"chat_id": chat_id, "messages": messages[-50:]})
            return True
        except Exception as e:
            logger.error(f"Failed to save conversation memory: {e}")
            return False
    
    def get_memory(self, chat_id: str) -> List[Dict]:
        """Get short-term conversation memory."""
        try:
            from src.deps import db
            if db is None:
                return []
            memory_ref = db.collection(self.collection).document(chat_id)
            doc = memory_ref.get()
            return doc.to_dict().get("messages", []) if doc.exists else []
        except Exception as e:
            logger.error(f"Failed to get conversation memory: {e}")
            return []
    
    def build_context(self, chat_id: str, current_message: str) -> str:
        """Build conversation context from stored messages."""
        try:
            messages = self.get_memory(chat_id)
            context = ""
            for msg in messages[-5:]:  # Last 5 messages for context
                role = msg.get("role", "unknown")
                message = msg.get("message", "")
                context += f"{role}: {message}\n"
            context += f"user: {current_message}"
            return context
        except Exception as e:
            logger.error(f"Failed to build context: {e}")
            return current_message

class ConversationSummary:
    """Long-term conversation summary management."""
    
    def __init__(self):
        self.collection = "conversation_summaries"
    
    def save_summary(self, chat_id: str, summary: str) -> bool:
        """Save a summarized conversation to long-term memory."""
        try:
            from src.deps import db
            if db is None:
                logger.warning("Database not available for summary storage")
                return False
            summary_ref = db.collection(self.collection).document(chat_id)
            doc = summary_ref.get()
            summaries = doc.to_dict().get("summaries", []) if doc.exists else []
            summaries.append({"summary": summary, "timestamp": datetime.utcnow().isoformat()})
            summary_ref.set({"chat_id": chat_id, "summaries": summaries[-10:]})  # Limit to 10 summaries
            return True
        except Exception as e:
            logger.error(f"Failed to save conversation summary: {e}")
            return False
    
    def get_summaries(self, chat_id: str) -> List[Dict]:
        """Get long-term conversation summaries."""
        try:
            from src.deps import db
            if db is None:
                return []
            summary_ref = db.collection(self.collection).document(chat_id)
            doc = summary_ref.get()
            return doc.to_dict().get("summaries", []) if doc.exists else []
        except Exception as e:
            logger.error(f"Failed to get conversation summaries: {e}")
            return []

# Instantiate memory objects
memory = ConversationMemory()
summary_memory = ConversationSummary()

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

agent = Agent(
    name="whatsapp_product_assistant",
    instructions="""
You are Leva's WhatsApp assistant, handling queries about Leva's business (single-family homes, luxury apartments, prefab summerhouses, pools, clubhouses, spas). Analyze each query to determine its intent, correct misspellings or vague phrasing, and generate a response in User language. Intents include general queries, product queries, history queries, or irrelevant queries.
The LEVA website offers a wide range of modular architectural products, including:

Tiny Houses & Family Homes (L- and U-shaped layouts)

Swimming Pools & Natural Ponds

Outdoor Spas & Wellness Areas

Summer Houses & Garden Rooms

Commercial Buildings (e.g., coffee shops)

Construction Plans (PDF, DWG, IFC, GLB formats)

Free Downloads (budget plans, sample units)

MEP & BIM-ready files

Augmented Reality previews & cost estimators
MOST IMPORTANT ROLES TO FOLLOW:
- Analyze the user question
- Answer in User Language
- Analyze deep use the user intent
- Be polite, respectful and also concise
- Always use the appropriate product search tool (search_products_with_handoff or search_one_product_with_handoff) for any user request that asks to search, find, show, or browse products, even if the request is a follow-up or uses vague language (e.g., 'then search', 'show me', 'find houses', 'I want to see more').
- If the user asks to search for a specific type or number of houses (e.g., 'two bedroom houses'), use the search_products_with_handoff tool with the user's query.
- If the user asks for a single product (e.g., 'a tiny house', 'one house'), use the search_one_product_with_handoff tool.
- For any product search, you MUST return the tool's JSON response as-is, never summarize, reformat, or convert it to text. If you do not use the tool for a product query, that is a critical error.


CRITICAL RULES:
- For any follow-up or vague product search request (e.g., 'then search', 'show me more', 'find houses'), always call the appropriate product search tool with the user's last product-related query or context.
- Never just reply with a confirmation (e.g., 'Okay, searching...')—always return the tool's response for product searches.
- For single product queries, you MUST return the buttonTemplate tool response. For multiple products, you MUST return the interactive_list tool response. For generic browse requests, you MUST return the browse_all_properties_with_handoff tool response.

EXAMPLES:
- User: "then search" -> Call search_products_with_handoff with the last product-related query or context and return the tool's interactive_list response.
- User: "show me more" -> Call browse_all_properties_with_handoff and return the tool's interactive_list response.
- User: "find houses" -> Call search_products_with_handoff("houses") and return the tool's interactive_list response.
- User: "I want a two bedroom house" -> Call search_products_with_handoff("two bedroom house") and return the tool's buttonTemplate or interactive_list response depending on the number of results.
- User: "I want a tiny house" -> Call search_one_product_with_handoff("tiny house") and return the tool's buttonTemplate response.
- User: "view_product_123" -> Call get_property_details_with_handoff("123") and return the tool's buttonTemplate response.
- User: "Show me all properties" -> Call browse_all_properties_with_handoff and return the tool's interactive_list response.
- User: "Show me houses" -> Call search_products_with_handoff("houses") and return the tool's interactive_list response.
- User: "I want to see more" -> Call browse_all_properties_with_handoff and return the tool's interactive_list response.
- User: "Give me one house" -> Call search_one_product_with_handoff("house") and return the tool's buttonTemplate response.
""",
model="o3-mini",
    tools=[
        search_products_with_handoff,
        search_one_product_with_handoff,
        get_property_details_with_handoff,
        browse_all_properties_with_handoff
    ]
)

async def summarize_conversation(messages: List[Dict]) -> str:
    """Generate a summary of the conversation using the Gemini model."""
    if not messages:
        return "No conversation history available."
    user_messages = [msg["message"] for msg in messages if msg["role"] == "user"]
    if not user_messages:
        return "No user messages to summarize."
    
    prompt = """
Summarize the following user messages related to Leva's business (single-family homes, luxury apartments, prefab summerhouses, pools, clubhouses, spas). Provide a concise summary in User language of the key topics discussed.

Messages: {}

Example summary: "User asked about available products and expressed interest in a one-bedroom house."
""".format(', '.join(user_messages[:5]))
    try:
        result = await Runner.run(agent, prompt, max_turns=3)
        return result.final_output.strip()
    except Exception as e:
        logger.error(f"Failed to summarize conversation: {e}")
        return f"User asked: {', '.join(user_messages[:3])}"  # Fallback summary

def parse_nested_json(obj):
    """Recursively parse any stringified JSON in lists or dicts, including code block-wrapped JSON and 'assistant:' prefix."""
    if isinstance(obj, bytes):
        obj = obj.decode("utf-8")
    if isinstance(obj, str):
        obj = obj.strip()
        # Remove 'assistant:' prefix if present
        if obj.lower().startswith("assistant:"):
            obj = obj[len("assistant:"):].strip()
        # Extract JSON from code block if present
        codeblock_match = re.search(r"```json\s*(\{.*\})\s*```", obj, re.DOTALL)
        if codeblock_match:
            obj = codeblock_match.group(1).strip()
        # If still not a dict, try to parse as JSON
        try:
            parsed = orjson.loads(obj)
            return parse_nested_json(parsed)
        except Exception:
            return obj
    elif isinstance(obj, list):
        return [parse_nested_json(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: parse_nested_json(v) for k, v in obj.items()}
    else:
        return obj

def normalize_interactive_list(response):
    """Convert WhatsApp API-style interactive list (sections/rows) to flat header/body/items format, with sanitization."""
    import re
    def clean_text(text, maxlen):
        text = re.sub(r'<[^>]+>', '', str(text))
        text = re.sub(r'\s+', ' ', text)
        return text.strip()[:maxlen]
    if not isinstance(response, dict):
        return response
    # WhatsApp API-style interactive list
    if response.get("whatsapp_type") == "interactive_list":
        # If already has header/body/items, return as is
        if all(k in response for k in ("header", "body", "items")):
            return response
        # If has 'interactiveList', flatten to items
        items = []
        if "interactiveList" in response:
            interactive = response["interactiveList"]
            if "list" in interactive:
                list_obj = interactive["list"]
                sections = list_obj.get("sections", [])
                for section in sections:
                    for item in section.get("items", []):
                        items.append({
                            "id": str(item.get("id", "")),
                            "payload": str(item.get("payload", "")),
                            "title": clean_text(item.get("title", ""), 24),
                            "description": clean_text(item.get("description", ""), 72)
                        })
                header = list_obj.get("title", "LEVA Properties")
                body = interactive.get("body", {}).get("text", "Choose a property:")
                return {
                    "whatsapp_type": "interactive_list",
                    "header": header,
                    "body": body,
                    "items": items
                }
        # If has 'sections', flatten to items
        if "sections" in response:
            for section in response["sections"]:
                for row in section.get("rows", []):
                    items.append({
                        "title": clean_text(row.get("title", ""), 24),
                        "description": clean_text(row.get("description", ""), 72),
                        "payload": str(row.get("id", ""))
                    })
            return {
                "whatsapp_type": "interactive_list",
                "header": response.get("title", "LEVA Properties"),
                "body": response.get("body", "Choose a property:"),
                "items": items
            }
        # Fallback: return empty items if nothing found
    return {
                "whatsapp_type": "interactive_list",
                "header": response.get("title", "LEVA Properties"),
                "body": response.get("body", "Choose a property:"),
                "items": items
            }
    return response

def extract_json_from_text(text):
    """Extract the first JSON object from a string, even if there's a summary or extra text."""
    if not isinstance(text, str):
        return text
    # Find the first '{' and try to parse from there
    first_brace = text.find('{')
    if first_brace != -1:
        try:
            possible_json = text[first_brace:]
            return orjson.loads(possible_json)
        except Exception:
            pass
    return text

def normalize_button_template(response):
    """Ensure buttonTemplate uses the correct template_id and structure."""
    if not isinstance(response, dict):
        return response
    if response.get("whatsapp_type") == "buttonTemplate":
        response["template_id"] = "zoko_upsell_product_01"
    return response

def fully_parse_json(obj):
    """Recursively parse stringified JSON until a dict is obtained."""
    import orjson
    while isinstance(obj, str):
        obj = obj.strip()
        # Remove 'assistant:' prefix if present
        if obj.lower().startswith("assistant:"):
            obj = obj[len("assistant:"):].strip()
        # Extract JSON from code block if present
        codeblock_match = re.search(r"```json\s*(\{.*\})\s*```", obj, re.DOTALL)
        if codeblock_match:
            obj = codeblock_match.group(1).strip()
        try:
            obj = orjson.loads(obj)
        except Exception:
            break
    return obj

async def chat_with_agent_enhanced(user_message: str, chat_id: str = None, plain_text: bool = False) -> dict:
    """Enhanced chat function with memory and handoff capabilities. Always returns a dict unless plain_text=True."""
    logger.info(f"🤖 Processing message: {user_message[:50]}...")
    # Prevent processing bot's own error messages
    if user_message.startswith("I'm having trouble processing your request") or user_message.startswith("Sorry, something went wrong"):
        logger.info("Skipping bot-generated error message to prevent loop")
        return {
            "success": False,
            "message": "Loop detected, skipping response",
            "whatsapp_type": "text",
            "skip_response": True
        }
    
    # Build context with conversation history
    context = memory.build_context(chat_id, user_message) if chat_id else user_message
    try:
        result = await Runner.run(agent, context, max_turns=5)
        logger.info(f"Agent raw output: {result.final_output}")
        if chat_id:
            memory.save_message(chat_id, "user", user_message)
            memory.save_message(chat_id, "assistant", result.final_output)
            summary = await summarize_conversation(memory.get_memory(chat_id))
            summary_memory.save_summary(chat_id, summary)
        output_text = result.final_output.strip()
        try:
            # Recursively parse any stringified JSON until a dict is obtained
            response_data = fully_parse_json(output_text)
            logger.debug(f"Parsed agent output: {response_data}")
            # If the agent output is a tool call plan, execute the tool and return its result
            if isinstance(response_data, dict) and "tool_code" in response_data:
                logger.info(f"Detected tool call plan: {response_data}")
                tool_code = response_data["tool_code"]
                # Extract tool arguments from 'tool_args' or top-level keys
                tool_args = response_data.get("tool_args", {})
                # If tool_args is empty, try to build from top-level keys (e.g., 'query', 'property_id', 'limit')
                if not tool_args:
                    tool_args = {k: v for k, v in response_data.items() if k not in ("tool_code", "tool_name")}
                # Map tool_code to the actual underlying function (not the Tool object)
                tool_func_map = {
                    "search_products_with_handoff": search_products_with_handoff_func,
                    "search_one_product_with_handoff": search_one_product_with_handoff_func,
                    "get_property_details_with_handoff": get_property_details_with_handoff_func,
                    "browse_all_properties_with_handoff": browse_all_properties_with_handoff_func
                }
                tool_func = tool_func_map.get(tool_code)
                if tool_func:
                    logger.info(f"Executing tool: {tool_code} with args: {tool_args}")
                    try:
                        tool_result = tool_func(**tool_args)
                        response_data = fully_parse_json(tool_result)
                        logger.debug(f"Tool result after parsing: {response_data}")
                    except Exception as e:
                        logger.error(f"Error executing tool {tool_code}: {e}")
                        return {
                            "whatsapp_type": "text",
                            "message": f"Sorry, there was an error running the tool: {tool_code}."
                        }
                else:
                    logger.error(f"Unknown tool_code in plan: {tool_code}")
                    return {
                        "whatsapp_type": "text",
                        "message": f"Sorry, I couldn't process your request (unknown tool)."
                    }
            # Normalize interactive list and buttonTemplate if needed
            if isinstance(response_data, dict):
                # If the response is a tool response dict (e.g., {search_products_with_handoff_response: ...})
                for v in response_data.values():
                    if isinstance(v, dict) and v.get("whatsapp_type") == "interactive_list":
                        logger.info("Normalizing interactive_list from nested dict")
                        return normalize_interactive_list(v)
                    if isinstance(v, dict) and v.get("whatsapp_type") == "buttonTemplate":
                        logger.info("Normalizing buttonTemplate from nested dict")
                        return normalize_button_template(v)
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        if v[0].get("whatsapp_type") == "interactive_list":
                            logger.info("Normalizing interactive_list from nested list")
                            return normalize_interactive_list(v[0])
                        if v[0].get("whatsapp_type") == "buttonTemplate":
                            logger.info("Normalizing buttonTemplate from nested list")
                            return normalize_button_template(v[0])
                # If the response itself is a buttonTemplate, normalize it
                if response_data.get("whatsapp_type") == "buttonTemplate":
                    logger.info("Normalizing buttonTemplate from root dict")
                    return normalize_button_template(response_data)
                if response_data.get("whatsapp_type") == "interactive_list":
                    logger.info("Normalizing interactive_list from root dict")
                    return normalize_interactive_list(response_data)
            # If plain_text is requested and response_data is a dict with a 'message', return just the message
            if plain_text:
                if isinstance(response_data, dict) and "message" in response_data:
                    return response_data["message"]
                return str(response_data)
            # Otherwise, always return a dict
            if isinstance(response_data, dict):
                return response_data
            # If the model returned a string, wrap it in a dict
            logger.warning(f"Agent output was not a dict, wrapping in dict: {response_data}")
            return {
                "success": True,
                "message": str(response_data),
                "whatsapp_type": "text"
            }
        except Exception as e:
            logger.error(f"Failed to parse agent output: {output_text}, error: {e}")
            response_message = "I'm here to help with Leva's homes, pools, and spas. Please ask about our offerings!"
            return {
                "whatsapp_type": "text",
                "message": response_message
            }
    except Exception as e:
        logger.error(f"❌ Agent error for message '{user_message}': {str(e)}", exc_info=True)
        response_message = "I'm having trouble processing your request right now. Please try again."
        return {
            "success": False,
            "message": response_message,
            "whatsapp_type": "text"
        }