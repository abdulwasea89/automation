import os
import json
import random
import time
from typing import List, Dict, Optional
from fastapi import FastAPI, Request, BackgroundTasks, Query, Form
from fastapi.responses import JSONResponse
from langdetect import detect, LangDetectException
from src.zoko_client import zoko_client
from src.tools import ProductDatabase

app = FastAPI(title="Simple Product Recommendation Bot")

# --- Load products from products.json ---
PRODUCTS_PATH = os.path.join(os.path.dirname(__file__), '../products.json')

def load_products() -> List[Dict]:
    # Load products from Firestore database instead of products.json
    return ProductDatabase.get_all_products(50)

# --- Semantic search for products ---
STOPWORDS = set([
    "the", "is", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "i", "you", "it", "my", "me", "your", "our", "us", "we", "they", "he", "she", "him", "her", "them", "this", "that", "these", "those"
])

def extract_keywords(query: str) -> List[str]:
    import re
    words = re.findall(r'\w+', query.lower())
    return [w for w in words if w not in STOPWORDS]

def semantic_search_products(query: str, products: List[Dict], limit: int = 10) -> List[Dict]:
    keywords = extract_keywords(query)
    scored = []
    for product in products:
        body = product.get("body_html", "").lower()
        title = product.get("title", "").lower()
        score = 0
        for kw in keywords:
            if kw in body or kw in title:
                score += 2
        if query.lower() in body or query.lower() in title:
            score += 3
        if score > 0:
            scored.append((score, product))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [p for _, p in scored[:limit]]

# --- Template formatting ---
def format_button_template(product: Dict) -> Dict:
    image_url = product.get("image_url") or product.get("images", [{}])[0].get("src") or "https://via.placeholder.com/400x300?text=Product"
    return {
        "template_id": "zoko_upsell_product_01",
        "template_args": [
            image_url,
            product.get("title", "Product"),
            f"PROD-{product.get('id', 'unknown')}",
            "view_details_payload"
        ]
    }

def format_interactive_list(products: List[Dict], message: str) -> Dict:
    items = []
    for product in products[:10]:
        title = product.get("title", "Product")[:20]
        items.append({
            "title": title,
            "description": f"{product.get('price', 'N/A')} - {product.get('product_type', '')}",
            "payload": f"view_{product.get('id', 'unknown')}"
        })
    return {
        "template_args": [
            "Available Products",
            message,
            json.dumps(items)
        ]
    }

# --- Webhook endpoint ---
@app.post("/webhook/zoko")
async def zoko_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    token: Optional[str] = Query(None),
    platformSenderId: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    customerName: Optional[str] = Form(None),
    platformTimestamp: Optional[str] = Form(None),
    type: Optional[str] = Form(None),
    id: Optional[str] = Form(None)
):
    start_time = time.time()
    try:
        # --- Parse incoming message ---
        try:
            body = await request.json()
            chat_id = body.get("platformSenderId") or body.get("chat_id") or body.get("sender")
            user_text = body.get("text") or body.get("message")
            customer_name = body.get("customerName") or body.get("customer_name")
        except Exception:
            chat_id = platformSenderId
            user_text = text
            customer_name = customerName
        if not chat_id or not user_text:
            return JSONResponse(content={"status": "ignored", "message": "Missing chat_id or text"})

        # --- Detect language (optional, not used in this simple version) ---
        try:
            detected_lang = detect(user_text)
        except LangDetectException:
            detected_lang = "en"
        user_lang = detected_lang or "en"

        # --- Product recommendation logic ---
        products = load_products()
        found_products = semantic_search_products(user_text, products, limit=10)

        # --- If no products found, show fallback message and random products ---
        if not found_products:
            fallback_message = "No products found for your query. Here are some you may like:"
            fallback_products = random.sample(products, min(5, len(products))) if products else []
            if fallback_products:
                template = format_interactive_list(fallback_products, fallback_message)
                await zoko_client.send_interactive_list(chat_id, template["template_args"])
            else:
                await zoko_client.send_text(chat_id, fallback_message)
            return JSONResponse(content={"status": "ok", "message": fallback_message, "products_found": 0})

        # --- If one product found, send button template ---
        if len(found_products) == 1:
            template = format_button_template(found_products[0])
            await zoko_client.send_button_template(chat_id, template["template_id"], template["template_args"])
            return JSONResponse(content={"status": "ok", "message": "Product recommendation sent (button template)", "products_found": 1})

        # --- If multiple products found, send interactive list ---
        template = format_interactive_list(found_products, f"Found {len(found_products)} products matching your query.")
        await zoko_client.send_interactive_list(chat_id, template["template_args"])
        return JSONResponse(content={"status": "ok", "message": "Product recommendations sent (interactive list)", "products_found": len(found_products)})

    except Exception as e:
        await zoko_client.send_text(chat_id, "Sorry, there was an error processing your request.")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# --- Health endpoint ---
@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}
