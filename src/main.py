import os
import json
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
from src.logger import get_logger, log_route, log_request, log_response, log_error, log_cache, log_agent
from src.openai_agent import chat_with_agent_enhanced
from collections import OrderedDict
from time import time
from typing import Dict
from src.product_loader import ProductLoader
from src.zoko_client import zoko_client
from src.zoko_utils import prepare_zoko_upsell_args
from src.tools import is_general_product_info_query, send_text_message
import re
import psutil
import gc
from src.cache import generate_cache_key, get_cached_response, cache_response, get_cache_stats
from fastapi.responses import ORJSONResponse
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
import logging
from starlette.middleware.trustedhost import TrustedHostMiddleware
from loguru import logger
import sys
from src.translation_utils import get_translation, detect_language
import re

def is_english(text):
    # Returns True if text is mostly ASCII and contains English words
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(1, len(text))
    # Simple English word check (could be improved)
    english_words = ["what", "do", "you", "offer", "services", "house", "plan", "hello", "hi", "how", "can", "i", "get", "the", "a", "an", "is", "are", "with", "for", "to", "in", "on", "and", "of", "or", "by", "from"]
    text_lower = text.lower()
    word_count = sum(1 for w in english_words if w in text_lower)
    return ascii_ratio > 0.9 and word_count > 0

# Remove all handlers associated with the root logger object.
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)


if os.getenv("PROFILE") == "1":
    try:
        from pyinstrument import Profiler
    except ImportError:
        Profiler = None
else:
    Profiler = None


class InterceptHandler(logging.Handler):
    def emit(self, record):
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_back and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())

logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)

# Intercept Uvicorn/FastAPI loggers
loggers = (
    "uvicorn",
    "uvicorn.access",
    "uvicorn.error",
    "fastapi",
    "asyncio",
    "starlette",
)
for logger_name in loggers:
    logging_logger = logging.getLogger(logger_name)
    logging_logger.handlers = []
    logging_logger.propagate = True

# Configure Loguru for multi-color console output
logger.remove()
logger.add(sys.stderr, colorize=True, format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")

# ---
# Loguru is now the main logger for the app, with multi-color output (no colorlog used).
# All logs from Uvicorn, FastAPI, and standard logging are routed through Loguru.
# ---

app = FastAPI(
    title="LEVA ASSISTANT",
    default_response_class=ORJSONResponse,
    # docs_url, redoc_url, openapi_url are NOT disabled so docs remain available
)

# Add GZIP compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add CORS middleware (allow all for now, restrict in prod as needed)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Add TrustedHostMiddleware for security (allow only your domains in production)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])  # Change to your domain(s) in prod

# Add custom security headers middleware
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
    return response

# Optional: Profiling middleware (enable with PROFILE=1)
if os.getenv("PROFILE") == "1":
    try:
        @app.middleware("http")
        async def profile_request(request, call_next):
            profiler = Profiler()
            profiler.start()
            response = await call_next(request)
            profiler.stop()
            print(profiler.output_text(unicode=True, color=True))
            return response
    except ImportError:
        logger.warning("pyinstrument not installed; profiling middleware not active.")

# ---
# PRODUCTION SERVER SETTINGS (for Docker, Cloud Run, etc.)
#
# Uvicorn (recommended for async):
#   uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4 --no-debug
#
# Gunicorn (recommended for multi-worker):
#   gunicorn -k uvicorn.workers.UvicornWorker src.main:app:app --workers 4 --timeout 300
#
# For HTTP/2, TLS, and keepalive, deploy behind Nginx or Caddy (see docs).
#
# ---

"""
PERFORMANCE BEST PRACTICES IMPLEMENTED
--------------------------------------
- GZip compression (FastAPI middleware)
- CORS middleware (FastAPI)
- ORJSONResponse for fast JSON serialization
- Async everywhere (endpoints, Firestore, HTTP calls)
- Background tasks for non-blocking work
- In-memory/Redis cache for responses
- Health and performance endpoints
- Security headers (custom + TrustedHostMiddleware)
- Profiling middleware (pyinstrument, opt-in)
- Logging set to WARNING for production
- Docs enabled for development and API consumers
- Production server settings for Uvicorn/Gunicorn
- Nginx/Caddy recommended for HTTP/2, TLS, keepalive

References:
- https://medium.com/@b.antoine.se/fastapi-under-the-hood-10-configuration-tweaks-for-blazing-fast-apis-54a51fd4c837
- https://kisspeter.github.io/fastapi-performance-optimization/
- https://loadforge.com/guides/fastapi-performance-tuning-tricks-to-enhance-speed-and-scalability
"""

class MessageDeduplicator:
    """Track processed message IDs to prevent duplicate processing."""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.processed_ids = OrderedDict()  # In-memory cache of message IDs
        self.max_size = max_size  # Maximum number of IDs to store
        self.ttl = ttl  # Time-to-live in seconds
    
    def is_duplicate(self, message_id: str) -> bool:
        """Check if a message ID has been processed recently."""
        current_time = time()
        # Remove expired entries
        while self.processed_ids and current_time - list(self.processed_ids.values())[0] > self.ttl:
            self.processed_ids.popitem(last=False)
        # Check if ID exists
        if message_id in self.processed_ids:
            logger.info(f"Duplicate message ID detected: {message_id}")
            return True
        # Add new ID
        self.processed_ids[message_id] = current_time
        # Trim cache if over max_size
        while len(self.processed_ids) > self.max_size:
            self.processed_ids.popitem(last=False)
        return False

deduplicator = MessageDeduplicator()

# Add a simple in-memory context for last shown product per chat_id
last_product_context = {}

class WhatsAppMessage(BaseModel):
    chat_id: str
    text: str
    customer_name: str = None
    lang: str = "en"

# Translation dictionary for UI/system messages
# TRANSLATIONS = {
#     "found_products": {
#         "en": "Found {count} products matching your query.",
#         "cs": "Nalezeno {count} produktů odpovídajících vašemu dotazu.",
#     },
#     "choose_option": {
#         "en": "Choose an option:",
#         "cs": "Vyberte možnost:",
#     },
#     "no_products": {
#         "en": "Sorry, could not find any products.",
#         "cs": "Omlouváme se, nenašli jsme žádné produkty.",
#     },
#     "product_list_title": {
#         "en": "LEVA Houses",
#         "cs": "LEVA Domy",
#     },
# }

# def get_translation(key, lang, **kwargs):
#     if lang not in TRANSLATIONS.get(key, {}):
#         lang = "en"
#     return TRANSLATIONS.get(key, {}).get(lang, TRANSLATIONS[key]["en"]).format(**kwargs)

def is_product_query(user_text: str) -> bool:
    keywords = [
        "house", "pool", "apartment", "product", "villa", "plan", "summerhouse", "clubhouse", "spa",
        "show me", "find", "search", "give me", "lynx", "rana", "sciurus", "oryx", "criceta", "coffee shop",  
    ]
    text = user_text.lower()
    return any(kw in text for kw in keywords)

def extract_product_query(user_text: str) -> str:
    # Remove common leading phrases and extra words
    text = user_text.lower()
    patterns = [
        r'^(i need|show me|find|search for|give me|i want|order|buy|can i get|please show|please find|view|see)\s+',
        r'[^a-zA-Z0-9\-/ ]',  # Remove non-alphanum except dash/slash/space
    ]
    for pat in patterns:
        text = re.sub(pat, '', text)
    # Remove extra spaces and capitalize
    text = text.strip()
    # Try to keep only the likely product name/ID (e.g., 'pavo 90')
    # Optionally, keep only first 4 words
    words = text.split()
    if len(words) > 4:
        text = ' '.join(words[:4])
    return text.title()

@app.post("/webhook/zoko")
async def zoko_webhook(request: Request, background_tasks: BackgroundTasks):
    """Zoko webhook endpoint with caching."""
    start_time = time()
    log_route("POST", "/webhook/zoko", endpoint="zoko_webhook")
    
    try:
        body = await request.json()
        
        # Skip non-user messages (e.g., delivery updates)
        event = body.get("event")
        if event != "message:user:in":
            log_request(message=f"Non-user event: {event}", event_type=event, skipped=True)
            return {"status": "skipped", "message": f"Ignored event {event}"}
        
        chat_id = body.get("platformSenderId")
        message_id = body.get("id")
        # Extract payload if present (for interactive list selection)
        payload_id = None
        # Zoko interactive list reply structure
        if "interactive" in body and "list_reply" in body["interactive"]:
            payload_id = body["interactive"]["list_reply"].get("id") or body["interactive"]["list_reply"].get("payload")
        # Fallback to text if no payload
        user_text = payload_id or body.get("text")
        
        # In zoko_webhook, after extracting user_text, also extract user language if available
        user_lang = detect_language(user_text)
        # Fallback: if langdetect returns a language not in ['en', 'cs'], use 'en'
        if user_lang not in ["en", "cs"]:
            user_lang = "en"
        # If the message is in English, force English
        if is_english(user_text):
            user_lang = "en"

        # --- Extract selected_product_id if payload_id is a digit ---
        selected_product_id = payload_id if payload_id and str(payload_id).isdigit() else None
        
        log_request(chat_id=chat_id, message=user_text, message_id=message_id, event=event)
        
        if not chat_id or not user_text or not message_id:
            log_error("VALIDATION", "Missing required fields", chat_id=chat_id, text=user_text, message_id=message_id)
            return {"status": "error", "message": "Missing chat_id, text, or id"}
        
        # Skip bot-generated or duplicate messages
        if (body.get("direction") != "FROM_CUSTOMER" or 
            user_text.startswith("I'm having trouble processing your request") or 
            user_text.startswith("Hello! 👋") or 
            deduplicator.is_duplicate(message_id)):
            log_request(chat_id=chat_id, message=user_text, skipped=True, reason="bot_or_duplicate")
            return {"status": "skipped", "message": "Bot or duplicate message ignored"}
        
        # Check cache for similar requests
        cache_key = generate_cache_key(user_text)
        cached_response = get_cached_response(cache_key)
        if cached_response:
            log_cache("HIT", cache_key, response_type=cached_response.get("whatsapp_type"))
            log_response(chat_id=chat_id, response_type="cached", cache_key=cache_key)
            
            # Send cached response
            if cached_response.get("whatsapp_type") == "text":
                await zoko_client.send_text(chat_id, cached_response.get("message", "I'm here to help!"))
            elif cached_response.get("whatsapp_type") == "buttonTemplate":
                await zoko_client.send_button_template(chat_id, cached_response["template_id"], cached_response["template_args"])
            elif cached_response.get("whatsapp_type") == "interactive_list":
                # Handle interactive list from cache
                interactive = cached_response.get("interactiveList")
                if interactive and "list" in interactive:
                    list_obj = interactive["list"]
                    sections = list_obj.get("sections", [])
                    items = []
                    for section in sections:
                        for item in section.get("items", []):
                            items.append({
                                "id": str(item.get("id", "")),
                                "payload": str(item.get("payload", "")),
                                "title": item.get("title", "")[:24],
                                "description": item.get("description", "")[:50]
                            })
                    # Filter out items with empty title or payload
                    items = [item for item in items if item["title"] and item["payload"]]
                    body = interactive["body"].get("text", "Choose an option:") if "body" in interactive else "Choose an option:"
                    await zoko_client.send_interactive_list(chat_id, list_obj.get("title", "LEVA Houses"), body, items)
            
            response_time = time() - start_time
            log_response(chat_id=chat_id, response_type="cached", response_time=f"{response_time:.3f}s")
            return {"status": "cached_response"}
        
        log_cache("MISS", cache_key)
        background_tasks.add_task(process_zoko_message, {
            "platformSenderId": chat_id,
            "text": user_text,
            "message_id": message_id,
            "cache_key": cache_key,
            "lang": user_lang,  # Pass detected language to processor
            "selected_product_id": selected_product_id
        })
        
        log_response(chat_id=chat_id, response_type="accepted", background_task=True)
        return {"status": "accepted"}
        
    except Exception as e:
        response_time = time() - start_time
        log_error("WEBHOOK", str(e), chat_id=chat_id if 'chat_id' in locals() else None, response_time=f"{response_time:.3f}s")
        return {"status": "error", "message": str(e)}

# Initialize the product loader once at startup
product_loader = ProductLoader("products_export.json")

async def process_zoko_message(payload: Dict):
    """Process Zoko webhook message with caching."""
    start_time = time()
    chat_id = payload["platformSenderId"]
    user_text = payload["text"]
    message_id = payload["message_id"]
    cache_key = payload.get("cache_key")
    lang = payload.get("lang", "en")  # Use detected language, default to en if missing

    log_agent("PROCESSOR", "started", chat_id=chat_id, message_id=message_id, message_preview=user_text[:50])

    try:
        # General product info check FIRST
        if is_general_product_info_query(user_text):
            GENERAL_PRODUCT_INFO_TEXT = (
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
            logger.info(f"[ZOKO DEBUG] General info query detected, sending info text to {chat_id}")
            await send_text_message(chat_id, GENERAL_PRODUCT_INFO_TEXT)
            return
        # Handle product selection from interactive list (payload is product id)
        if 'selected_product_id' in payload and payload['selected_product_id']:
            selected_id = payload['selected_product_id']
            selected_product = product_loader.get_by_id(selected_id)
            if selected_product:
                import re
                name = selected_product.get('name', '')
                match = re.match(r"^([A-Za-z]+\s*\d+)", name)
                base_name = match.group(1).strip() if match else name
                all_variants = [p for p in product_loader.search(base_name, lang=lang, max_results=10)
                                if p.get('id') != selected_product.get('id') and p.get('name', '').startswith(base_name)]
                variants = [v for v in all_variants if v.get('name') != name][:3]
                args = prepare_zoko_upsell_args(selected_product)
                logger.info(f"[ZOKO DEBUG] Product dict for template: {json.dumps(selected_product, indent=2, ensure_ascii=False)}")
                logger.info(f"[ZOKO DEBUG] Final template args: {args}")
                if args:
                    await zoko_client.send_button_template(chat_id, selected_product.get('template_id', 'zoko_upsell_product_01'), args)
                else:
                    logger.error(f"Skipping product with missing template args: {selected_product}")
                if not variants:
                    related = product_loader.search(name, lang=lang, max_results=10)
                    related = [p for p in related if p.get('id') != selected_product.get('id')][:3]
                    variants = related
                for v in variants:
                    await asyncio.sleep(0.5)
                    args = prepare_zoko_upsell_args(v)
                    logger.info(f"[ZOKO DEBUG] Product dict for template: {json.dumps(v, indent=2, ensure_ascii=False)}")
                    logger.info(f"[ZOKO DEBUG] Final template args: {args}")
                    if args:
                        await zoko_client.send_button_template(chat_id, v.get('template_id', 'zoko_upsell_product_01'), args)
                    else:
                        logger.error(f"Skipping variant with missing template args: {v}")
                response = {"success": True, "message": "Product and variants/related sent.", "whatsapp_type": "buttonTemplate"}
                if cache_key:
                    cache_response(cache_key, response)
                return
            else:
                await zoko_client.send_text(chat_id, "Sorry, I couldn't find the product you selected. Please try again.")
                return

        # All other queries: let the agent decide (including all product-related queries)
        log_agent("OPENAI_AGENT", "processing", chat_id=chat_id, message=user_text)

        response = await chat_with_agent_enhanced(user_text, chat_id=chat_id, lang=lang)
        # Always try to parse response as JSON if it's a string
        import json
        if isinstance(response, str):
            try:
                response_data = json.loads(response)
            except Exception:
                response_data = None
        else:
            response_data = response

        # If the response is a list of buttonTemplates, send each one by one, re-searching after each batch and excluding already sent products
        if isinstance(response_data, list) and all(isinstance(r, dict) and r.get('whatsapp_type') == 'buttonTemplate' for r in response_data):
            sent_ids = set()
            user_query = user_text
            lang_query = lang
            max_per_batch = 3
            while True:
                products = product_loader.search(user_query, lang=lang_query, max_results=10)
                new_products = [p for p in products if p.get('id') not in sent_ids]
                if not new_products:
                    break
                batch = new_products[:max_per_batch]
                for p in batch:
                    sent_ids.add(p.get('id'))
                    args = prepare_zoko_upsell_args(p)
                    logger.info(f"[ZOKO DEBUG] Product dict for template: {json.dumps(p, indent=2, ensure_ascii=False)}")
                    logger.info(f"[ZOKO DEBUG] Final template args: {args}")
                    await zoko_client.send_button_template(
                        chat_id,
                        p.get('template_id', 'zoko_upsell_product_01'),
                        args
                    )
                    await asyncio.sleep(1)
                if len(batch) < max_per_batch:
                    break
            return
        # --- NEW LOGIC: handle direct interactive_list dict (header/body/items) ---
        elif isinstance(response_data, dict) and response_data.get('whatsapp_type') == 'interactive_list' and all(k in response_data for k in ('header', 'body', 'items')):
            # Defensive: filter items to required fields and Zoko limits
            items = []
            seen_payloads = set()
            for item in response_data['items']:
                payload = str(item.get('payload', ''))[:200]
                title = str(item.get('title', ''))[:24]
                description = str(item.get('description', ''))[:72]
                if not payload or not title or payload in seen_payloads:
                    continue
                seen_payloads.add(payload)
                items.append({
                    'title': title,
                    'description': description,
                    'payload': payload
                })
            if items:
                section_title = str(response_data['header'])[:24] if response_data.get('header') else 'LEVA Houses'
                list_title = section_title
                body = str(response_data['body'])[:72] if response_data.get('body') else 'Choose an option:'
                footer = 'Powered by Zoko'
                # Debug log the final payload
                logger.info(f"[ZOKO DEBUG] Interactive list send: header={list_title}, body={body}, section_title={section_title}, items={json.dumps(items, ensure_ascii=False)}")
                await zoko_client.send_interactive_list(
                    chat_id,
                    list_title,
                    body,
                    items,
                    section_title=section_title,
                    footer=footer
                )
                return
            else:
                await zoko_client.send_text(chat_id, "Sorry, no products found.")
                return
        # --- END NEW LOGIC ---
        elif isinstance(response_data, dict) and response_data.get('whatsapp_type') == 'buttonTemplate':
            if 'template_args' in response_data:
                args = response_data['template_args']
                logger.info(f"[ZOKO DEBUG] Using provided template_args: {args}")
            else:
                args = prepare_zoko_upsell_args(response_data)
                logger.info(f"[ZOKO DEBUG] Product dict for template: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                logger.info(f"[ZOKO DEBUG] Final template args: {args}")
            await zoko_client.send_button_template(chat_id, response_data.get('template_id', 'zoko_upsell_product_01'), args)
            return
        elif isinstance(response_data, dict) and response_data.get('whatsapp_type') == 'interactive_list':
            interactive = response_data.get('interactiveList')
            if interactive and 'list' in interactive:
                list_obj = interactive['list']
                body = interactive.get('body', {}).get('text', 'Choose an option:')
                sections = list_obj.get('sections', [])
                items = []
                for section in sections:
                    for item in section.get('items', []):
                        desc = item.get('description', '')
                        if desc and len(desc) > 50:
                            desc = desc[:47] + '...'
                        items.append({
                            'payload': str(item.get('payload', '')),
                            'title': item.get('title', '')[:24],
                            'description': desc or 'No description available'
                        })
                items = [item for item in items if item['title'] and item['payload']]
                await zoko_client.send_interactive_list(chat_id, list_obj.get('title', 'LEVA Houses'), body, items)
                return
        # Fallback: if the user query looks like a product query but agent did not return a template, call the product search tool directly
        from src.handoff_tools import search_products_with_handoff_func, search_one_product_with_handoff_func
        from src.openai_agent import fully_parse_json
        if is_product_query(user_text):
            # Only fallback if response is not a buttonTemplate or interactive_list
            is_template = False
            if isinstance(response_data, dict) and response_data.get('whatsapp_type') in ('buttonTemplate', 'interactive_list'):
                is_template = True
            if not is_template:
                # Clean the query for better matching
                cleaned_query = extract_product_query(user_text)
                logger.info(f"[ZOKO DEBUG] Fallback original query: {user_text} | Cleaned: {cleaned_query}")
                # If the query is a list/all/browse request, skip single product and go straight to interactive list
                list_keywords = ["all", "list", "show me all", "browse", "see all"]
                cleaned_query_lower = cleaned_query.lower()
                if any(kw in cleaned_query_lower for kw in list_keywords):
                    response_fallback = search_products_with_handoff_func(cleaned_query, lang=lang)
                    logger.info(f"[ZOKO DEBUG] Fallback tool response (multi-product): {response_fallback}")
                    response_fallback_data = fully_parse_json(response_fallback)
                    if response_fallback_data.get('whatsapp_type') == 'interactive_list':
                        interactive = response_fallback_data.get('interactiveList')
                        if interactive and 'list' in interactive:
                            list_obj = interactive['list']
                            body = interactive.get('body', {}).get('text', 'Choose an option:')
                            sections = list_obj.get('sections', [])
                            items = []
                            for section in sections:
                                for item in section.get('items', []):
                                    desc = item.get('description', '')
                                    if desc and len(desc) > 50:
                                        desc = desc[:47] + '...'
                                    items.append({
                                        'payload': str(item.get('payload', '')),
                                        'title': item.get('title', '')[:24],
                                        'description': desc or 'No description available'
                                    })
                            items = [item for item in items if item['title'] and item['payload']]
                            logger.info(f"[ZOKO DEBUG] Fallback interactive list items: {items}")
                            await zoko_client.send_interactive_list(chat_id, list_obj.get('title', 'LEVA Houses'), body, items)
                            return
                    logger.error(f"[ZOKO ERROR] No interactive list found for query: {user_text}")
                    await zoko_client.send_text(chat_id, "Sorry, no products found.")
                    return
                # Otherwise, try single product first, then multi-product
                response_fallback = search_one_product_with_handoff_func(cleaned_query, lang=lang)
                logger.info(f"[ZOKO DEBUG] Fallback tool response (single product): {response_fallback}")
                response_fallback_data = fully_parse_json(response_fallback)
                if response_fallback_data.get('whatsapp_type') == 'buttonTemplate':
                    args = prepare_zoko_upsell_args(response_fallback_data)
                    logger.info(f"[ZOKO DEBUG] Fallback template args: {args}")
                    await zoko_client.send_button_template(chat_id, response_fallback_data.get('template_id', 'zoko_upsell_product_01'), args)
                    return
                # Otherwise, fallback to multi-product search
                response_fallback = search_products_with_handoff_func(cleaned_query, lang=lang)
                logger.info(f"[ZOKO DEBUG] Fallback tool response (multi-product): {response_fallback}")
                response_fallback_data = fully_parse_json(response_fallback)
                if response_fallback_data.get('whatsapp_type') == 'interactive_list':
                    interactive = response_fallback_data.get('interactiveList')
                    if interactive and 'list' in interactive:
                        list_obj = interactive['list']
                        body = interactive.get('body', {}).get('text', 'Choose an option:')
                        sections = list_obj.get('sections', [])
                        items = []
                        for section in sections:
                            for item in section.get('items', []):
                                desc = item.get('description', '')
                                if desc and len(desc) > 50:
                                    desc = desc[:47] + '...'
                                items.append({
                                    'payload': str(item.get('payload', '')),
                                    'title': item.get('title', '')[:24],
                                    'description': desc or 'No description available'
                                })
                        items = [item for item in items if item['title'] and item['payload']]
                        logger.info(f"[ZOKO DEBUG] Fallback interactive list items: {items}")
                        await zoko_client.send_interactive_list(chat_id, list_obj.get('title', 'LEVA Houses'), body, items)
                        return
                # If fallback fails, log and send a generic error
                logger.error(f"[ZOKO ERROR] No product or interactive list found for query: {user_text}")
                await zoko_client.send_text(chat_id, "Sorry, no products found.")
                return
        # For all other cases (including greetings), send the agent's text response
        await zoko_client.send_text(chat_id, response_data.get('message', str(response_data)))
        return

    except Exception as e:
        response_time = time() - start_time
        log_error("PROCESSOR", str(e), chat_id=chat_id, message_id=message_id, response_time=f"{response_time:.3f}s")
        await zoko_client.send_text(chat_id, "Sorry, something went wrong.")

@app.get("/")
def hello():
    log_route("GET", "/", endpoint="hello")
    log_response(response_type="hello", message="App is good")
    return {
        "app is good"
    }

@app.get("/health")
def health_check():
    """Health check endpoint for monitoring."""
    start_time = time()
    log_route("GET", "/health", endpoint="health_check")
    
    response_data = {
        "status": "healthy",
        "timestamp": time(),
        "environment": os.getenv("ENVIRONMENT", "development")
    }
    
    response_time = time() - start_time
    log_response(response_type="health", response_time=f"{response_time:.3f}s", status="healthy")
    return response_data

@app.get("/cache/stats")
def cache_stats():
    """Get cache statistics for monitoring."""
    start_time = time()
    log_route("GET", "/cache/stats", endpoint="cache_stats")
    
    stats = get_cache_stats()
    response_time = time() - start_time
    log_response(response_type="cache_stats", response_time=f"{response_time:.3f}s", stats=stats)
    return stats

@app.get("/performance")
def performance_metrics():
    """Get performance metrics."""
    start_time = time()
    log_route("GET", "/performance", endpoint="performance_metrics")
    
    # Force garbage collection
    gc.collect()
    
    metrics = {
        "memory_usage_mb": psutil.Process().memory_info().rss / 1024 / 1024,
        "cpu_percent": psutil.Process().cpu_percent(),
        "cache_stats": get_cache_stats(),
        "deduplicator_size": len(deduplicator.processed_ids),
        "environment": os.getenv("ENVIRONMENT", "development")
    }
    
    response_time = time() - start_time
    log_response(response_type="performance", response_time=f"{response_time:.3f}s", memory_mb=f"{metrics['memory_usage_mb']:.2f}")
    return metrics

# Production server startup
if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or default to 8080 (Cloud Run standard)
    port = int(os.getenv("PORT", 8080))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Production settings for Cloud Run
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,  # Disable reload in production
        workers=1,     # Single worker for Cloud Run
        log_level="info",
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*"
    )