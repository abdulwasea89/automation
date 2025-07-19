import os
import orjson
import logging
import asyncio
from typing import List, Dict
from datetime import datetime
from dotenv import load_dotenv
from agents import Runner, Agent, AsyncOpenAI, OpenAIChatCompletionsModel, RunConfig
from src.logger import get_logger, log_agent, log_error
from src.handoff_tools import (
    search_products_with_handoff,
    search_one_product_with_handoff,
    search_products_with_handoff_func,
    search_one_product_with_handoff_func,
)
import re
from time import time
from src.product_loader import product_loader

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
    instructions="""# Leva's WhatsApp Business Assistant Prompt

This prompt defines the behavior of Leva's WhatsApp Business Assistant, which exclusively answers questions about Leva's business, products, and services. **The most critical requirement is that the assistant must always respond in the user's language when supported**, localizing all responses accordingly. The assistant supports a restricted set of languages: English, Czech, and Chinese. If the user's language is not supported, it will respond in English and notify the user.

## MOST IMPORTANT RULES TO FOLLOW:
- Always anwser in User language it does not matter how you hillucinate

## General Principles
- **Scope**: Exclusively answer questions related to Leva's business, products, and services.
- **Restrictions**: Politely refuse unrelated questions with: "Sorry, I can only answer questions about Leva's business, products, and services" in the user's language (or English if unsupported).
- **Decision Making**: Use your own reasoning to select the appropriate tool and determine when to use it.
- **Language Handling**: 
  - Detect the user's language from their input.
  - Respond in the user's language if it is English, Czech, or Chinese.
  - If the language is not supported, respond in English with: "Sorry, I don’t support your language yet. I’ll respond in English instead."

## Tool Usage Rules
- **General Product Questions** (e.g., "What products do you have?"):
  - Call `get_general_product_info` and return its response as text in the user's language (English if unsupported).
- **Requests for All Products** (e.g., "Show me all products"):
  - Call the product search tool and return an interactive list (max 10 products) in the user's language (English if unsupported).
- **Specific Product Requests** (e.g., "I need PAVO 90"):
  - Call the product tool and return its output as-is (buttonTemplate dict), localized to the user's language (English if unsupported).
- **Vague Follow-ups** (e.g., "Show me more"):
  - Use the last product-related context to decide whether to show an interactive list or a product template, in the user's language (English if unsupported).
- **Greetings** (e.g., "Hi"):
  - Respond with a friendly greeting in the user's language (English if unsupported).
- **Other Queries**:
  - Use best judgment to respond or select a tool, but never answer unrelated questions.
  - Localize all responses to the user's language (English if unsupported).

## Critical Rules
- **Product Display**: Only show products when explicitly requested by the user.
- **Tool Output**: Return tool responses as-is (no summarizing or reformatting), localized to the user's language (English if unsupported).
- **Product Queries**: For specific product requests, call the product tool and return its output as-is (buttonTemplate dict), never as a text summary.
- **Language Consistency**: Always prioritize responding in the user's language (English, Czech, or Chinese). Use English and notify the user if their language isn’t supported.
- **Autonomy**: Rely on your own reasoning for tool selection and usage; the backend will not intervene.

## Examples
- **User**: "What products do you have?" (in English)  
  **Response**: Call `get_general_product_info` and return its text response in English.
- **User**: "Jaké máte produkty?" (in Czech)  
  **Response**: Call `get_general_product_info` and return its text response in Czech.
- **User**: "你们有哪些产品?" (in Chinese)  
  **Response**: Call `get_general_product_info` and return its text response in Chinese.
- **User**: "Quels produits avez-vous?" (in French, unsupported)  
  **Response**: "Sorry, I don’t support your language yet. I’ll respond in English instead." + Call `get_general_product_info` and return its text response in English.
- **User**: "What is 2+2?" (in English)  
  **Response**: "Sorry, I can only answer questions about Leva's business, products, and services" in English.""",
    model="o3-mini",
    tools=[
        search_products_with_handoff,
        search_one_product_with_handoff
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
                        payload_val = str(item.get("payload", ""))
                        items.append({
                            "id": payload_val,
                            "payload": payload_val,
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

def format_product_with_variants_button_template(product: dict) -> dict:
    """
    Format a product (with variants) as a WhatsApp buttonTemplate.
    """
    variants = product.get('variants', [])
    variant_titles = [v.get('Option1 Value') for v in variants if v.get('Option1 Value')]
    variant_str = f"Variants: {', '.join(variant_titles)}" if variant_titles else ""
    description = product.get('description', '')
    if variant_str:
        description = f"{description}\n\n{variant_str}"
    return {
        "whatsapp_type": "buttonTemplate",
        "template_id": "zoko_upsell_product_01",
        "header": product.get('name', product.get('Title', 'Product')),
        "body": description,
        "image": product.get('image_url'),
        "buttons": [
            {"type": "reply", "title": "View Details", "payload": product.get('id', '')}
        ]
    }

def send_products_with_variants_paginated(handles: list, lang: str = 'en', page: int = 1, page_size: int = 3) -> list:
    """
    Return a list of up to 3 buttonTemplates for products (with variants).
    """
    products = product_loader.get_products_paginated(handles, lang=lang, page=page, page_size=page_size)
    return [format_product_with_variants_button_template(prod) for prod in products]

def is_english(text):
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(1, len(text))
    english_words = ["what", "do", "you", "offer", "services", "house", "plan", "hello", "hi", "how", "can", "i", "get", "the", "a", "an", "is", "are", "with", "for", "to", "in", "on", "and", "of", "or", "by", "from"]
    text_lower = text.lower()
    word_count = sum(1 for w in english_words if w in text_lower)
    return ascii_ratio > 0.9 and word_count > 0

async def chat_with_agent_enhanced(user_message: str, chat_id: str = None, lang: str = "en", plain_text: bool = False) -> dict:
    """Enhanced chat function with memory and handoff capabilities. Always returns a dict unless plain_text=True."""
    start_time = time()
    log_agent("CHAT", "started", chat_id=chat_id, message_preview=user_message[:50], lang=lang)
    
    # Prevent processing bot's own error messages
    if user_message.startswith("I'm having trouble processing your request") or user_message.startswith("Sorry, something went wrong"):
        log_agent("CHAT", "skipping_bot_message", chat_id=chat_id, reason="loop_prevention")
        return {
            "success": False,
            "message": "Loop detected, skipping response",
            "whatsapp_type": "text",
            "skip_response": True
        }
    
    # Fallback: if lang is not 'en' or 'cs', use 'en'
    if lang not in ["en", "cs"]:
        lang = "en"
    # If the message is in English, force English
    if is_english(user_message):
        lang = "en"
    
    # Build context with conversation history
    context = memory.build_context(chat_id, user_message) if chat_id else user_message
    try:
        log_agent("RUNNER", "executing", chat_id=chat_id, max_turns=15, lang=lang)
        result = await Runner.run(agent, context, max_turns=15)
        log_agent("RUNNER", "completed", chat_id=chat_id, output_length=len(result.final_output), lang=lang)
        
        # Optimized memory operations - only save essential data
        if chat_id:
            # Save messages asynchronously without blocking
            try:
                memory.save_message(chat_id, "user", user_message)
                memory.save_message(chat_id, "assistant", result.final_output)
                # Only generate summary every 5 messages to reduce overhead
                recent_messages = memory.get_memory(chat_id)
                if len(recent_messages) % 5 == 0:  # Every 5th message
                    log_agent("MEMORY", "generating_summary", chat_id=chat_id, message_count=len(recent_messages))
                    summary = await summarize_conversation(recent_messages)
                    summary_memory.save_summary(chat_id, summary)
            except Exception as e:
                log_error("MEMORY", str(e), chat_id=chat_id)
        
        output_text = result.final_output.strip()
        try:
            # Recursively parse any stringified JSON until a dict is obtained
            response_data = fully_parse_json(output_text)
            log_agent("PARSING", "json_parsed", chat_id=chat_id, is_dict=isinstance(response_data, dict), lang=lang)
            # If the agent output is a tool call plan, execute the tool and return its result
            if isinstance(response_data, dict) and "tool_code" in response_data:
                log_agent("TOOL", "executing_plan", chat_id=chat_id, tool_code=response_data["tool_code"], lang=lang)
                tool_code = response_data["tool_code"]
                # Extract tool arguments from 'tool_args' or top-level keys
                tool_args = response_data.get("tool_args", {})
                # Always inject lang into tool_args
                tool_args["lang"] = lang
                # Map tool_code to the actual underlying function (not the Tool object)
                tool_func_map = {
                    "search_products_with_handoff": search_products_with_handoff_func,
                    "search_one_product_with_handoff": search_one_product_with_handoff_func,
                }
                tool_func = tool_func_map.get(tool_code)
                if tool_func:
                    log_agent("TOOL", "executing", chat_id=chat_id, tool_code=tool_code, args=tool_args, lang=lang)
                    try:
                        tool_result = tool_func(**tool_args)
                        response_data = fully_parse_json(tool_result)
                        log_agent("TOOL", "completed", chat_id=chat_id, tool_code=tool_code, success=True, lang=lang)
                    except Exception as e:
                        log_error("TOOL", str(e), chat_id=chat_id, tool_code=tool_code, lang=lang)
                        return {
                            "whatsapp_type": "text",
                            "message": f"Sorry, there was an error running the tool: {tool_code}."
                        }
                else:
                    log_error("TOOL", f"Unknown tool_code: {tool_code}", chat_id=chat_id, lang=lang)
                    return {
                        "whatsapp_type": "text",
                        "message": f"Sorry, I couldn't process your request (unknown tool)."
                    }
            
            # Normalize interactive list and buttonTemplate if needed
            if isinstance(response_data, dict):
                # If the response is a tool response dict (e.g., {search_products_with_handoff_response: ...})
                for v in response_data.values():
                    if isinstance(v, dict) and v.get("whatsapp_type") == "interactive_list":
                        log_agent("NORMALIZE", "interactive_list_from_nested", chat_id=chat_id, lang=lang)
                        return normalize_interactive_list(v)
                    if isinstance(v, dict) and v.get("whatsapp_type") == "buttonTemplate":
                        log_agent("NORMALIZE", "buttonTemplate_from_nested", chat_id=chat_id, lang=lang)
                        return normalize_button_template(v)
                    if isinstance(v, list) and v and isinstance(v[0], dict):
                        if v[0].get("whatsapp_type") == "interactive_list":
                            log_agent("NORMALIZE", "interactive_list_from_nested_list", chat_id=chat_id, lang=lang)
                            return normalize_interactive_list(v[0])
                        if v[0].get("whatsapp_type") == "buttonTemplate":
                            log_agent("NORMALIZE", "buttonTemplate_from_nested_list", chat_id=chat_id, lang=lang)
                            return normalize_button_template(v[0])
                # If the response itself is a buttonTemplate, normalize it
                if response_data.get("whatsapp_type") == "buttonTemplate":
                    log_agent("NORMALIZE", "buttonTemplate_from_root", chat_id=chat_id, lang=lang)
                    return normalize_button_template(response_data)
                if response_data.get("whatsapp_type") == "interactive_list":
                    log_agent("NORMALIZE", "interactive_list_from_root", chat_id=chat_id, lang=lang)
                    return normalize_interactive_list(response_data)
            
            # If plain_text is requested and response_data is a dict with a 'message', return just the message
            if plain_text:
                if isinstance(response_data, dict) and "message" in response_data:
                    return response_data["message"]
                return str(response_data)
            
            # Otherwise, always return a dict
            if isinstance(response_data, dict):
                response_time = time() - start_time
                log_agent("CHAT", "completed", chat_id=chat_id, response_type=response_data.get("whatsapp_type"), response_time=f"{response_time:.3f}s", lang=lang)
                return response_data
            
            # If the model returned a string, wrap it in a dict
            log_agent("CHAT", "wrapping_string", chat_id=chat_id, response_type="text", lang=lang)
            return {
                "success": True,
                "message": str(response_data),
                "whatsapp_type": "text"
            }
        except Exception as e:
            log_error("PARSING", str(e), chat_id=chat_id, output_text=output_text[:100], lang=lang)
            response_message = "I'm here to help with Leva's homes, pools, and spas. Please ask about our offerings!"
            return {
                "whatsapp_type": "text",
                "message": response_message
            }
    except Exception as e:
        response_time = time() - start_time
        log_error("CHAT", str(e), chat_id=chat_id, response_time=f"{response_time:.3f}s", lang=lang)
        response_message = "I'm having trouble processing your request right now. Please try again."
        return {
            "success": False,
            "message": response_message,
            "whatsapp_type": "text"
        }


async def search_and_respond_to_user(user_input: str, chat_id: str = "test", lang: str = "en") -> dict:
    """
    Given user input, returns either an interactive list or a product template (buttonTemplate) as WhatsApp dict.
    """
    return await chat_with_agent_enhanced(user_input, chat_id=chat_id, lang=lang)