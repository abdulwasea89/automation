import os
import sys
import asyncio
import json
import time
from datetime import datetime
from typing import List, Dict, Optional, Any
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Form, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from src.config import settings
from src.deps import db as gcp_db
from src.logger import get_logger
from src.openai_agent import chat_with_agent_enhanced
from src.zoko_client import zoko_client
from src.zoko_utils import zoko_utils
from src.gcp import ChatMemory
from src.tools import ProductDatabase, search_database_func

logger = get_logger("app")

app = FastAPI(title="LEVA ASSISTANT")

class WhatsAppMessage(BaseModel):
    chat_id: str = Field(..., description="WhatsApp chat ID")
    text: str = Field(..., description="Message text")
    customer_name: Optional[str] = Field(None, description="Customer name")
    lang: str = Field("en", description="Language code")

class ZokoWebhookPayload(BaseModel):
    """Zoko webhook payload model for compatibility."""
    id: Optional[str] = None
    platformSenderId: str = Field(..., description="WhatsApp number")
    platformTimestamp: Optional[str] = None
    text: Optional[str] = None
    customerName: Optional[str] = None
    type: Optional[str] = None

class BroadcastResponse(BaseModel):
    """Response model for webhook endpoints."""
    status: str

class ConversationManager:
    """Production-level conversation history management."""
    
    def __init__(self):
        self.chat_memory = ChatMemory()
    
    def save_conversation(self, chat_id: str, role: str, message: str, metadata: Dict = None) -> bool:
        """Save conversation message to Firebase with metadata."""
        try:
            # Save to chat memory
            self.chat_memory.save_message(chat_id, role, message)
            
            # Save detailed conversation data
            if gcp_db:
                conversation_ref = gcp_db.collection("conversations").document(chat_id)
                
                conversation_data = {
                    "chat_id": chat_id,
                    "last_message": {
                        "role": role,
                        "message": message,
                        "timestamp": datetime.now().isoformat(),
                        "metadata": metadata or {}
                    },
                    "last_updated": datetime.now().isoformat(),
                    "message_count": 0
                }
                
                # Update message count
                doc = conversation_ref.get()
                if doc.exists:
                    current_data = doc.to_dict()
                    conversation_data["message_count"] = current_data.get("message_count", 0) + 1
                
                conversation_ref.set(conversation_data, merge=True)
                logger.info(f"💾 Saved conversation for {chat_id} - {role}: {message[:50]}...")
                return True
            else:
                logger.warning("Firebase not available for detailed conversation saving")
                return False
                
        except Exception as e:
            logger.error(f"Failed to save conversation for {chat_id}: {e}")
            return False
    
    def get_conversation_history(self, chat_id: str, limit: int = 10) -> List[Dict]:
        """Get recent conversation history for context."""
        try:
            history = self.chat_memory.load_history(chat_id)
            return history[-limit:] if history else []
        except Exception as e:
            logger.error(f"Failed to load conversation history for {chat_id}: {e}")
            return []
    
    def get_customer_profile(self, chat_id: str) -> Dict:
        """Get customer profile and preferences."""
        try:
            if gcp_db:
                profile_ref = gcp_db.collection("customer_profiles").document(chat_id)
                doc = profile_ref.get()
                if doc.exists:
                    return doc.to_dict()
            
            return {
                "chat_id": chat_id,
                "created_at": datetime.now().isoformat(),
                "preferences": {"language": "en", "product_categories": [], "budget_range": None},
                "interaction_count": 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get customer profile for {chat_id}: {e}")
            return {"chat_id": chat_id, "error": str(e)}

class ProductService:
    """Production-level product service with Firebase integration."""
    
    def __init__(self):
        self.db = ProductDatabase()
    
    def search_products(self, query: str, limit: int = 10) -> Dict:
        """Search products with comprehensive error handling."""
        try:
            logger.info(f"🔍 Searching products for: {query}")
            result = search_database_func("search", query=query, limit=limit)
            
            if isinstance(result, str):
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    return {"success": False, "message": "Error parsing search results", "products": []}
            else:
                return result
                
        except Exception as e:
            logger.error(f"Product search failed for '{query}': {e}")
            return {"success": False, "message": "Sorry, I'm having trouble searching products right now.", "products": []}

class WhatsAppService:
    """Production-level WhatsApp messaging service."""
    
    def __init__(self):
        self.client = zoko_client
        self.utils = zoko_utils
    
    def send_rich_response(self, chat_id: str, response_data: Dict) -> bool:
        """Send rich WhatsApp response with proper template selection."""
        try:
            whatsapp_type = response_data.get("whatsapp_type", "text")
            if whatsapp_type == "buttonTemplate":
                # For multiple products (list)
                if "product_cards" in response_data:
                    success = True
                    for card in response_data["product_cards"]:
                        template_id = card["template_id"]
                        template_args = card["template_args"]
                        payload = {
                            "channel": "whatsapp",
                            "type": "buttonTemplate",
                            "templateId": template_id,
                            "templateArgs": template_args,
                            "recipient": chat_id
                        }
                        sent = self.client.send_button_template(chat_id, template_id, template_args)
                        success = success and sent
                    return success
                elif "product_card" in response_data:
                    card = response_data["product_card"]
                    template_id = card["template_id"]
                    template_args = card["template_args"]
                    payload = {
                        "channel": "whatsapp",
                        "type": "buttonTemplate",
                        "templateId": template_id,
                        "templateArgs": template_args,
                        "recipient": chat_id
                    }
                    return self.client.send_button_template(chat_id, template_id, template_args)
                elif "template" in response_data:
                    template = response_data["template"]
                    template_id = template.get("template_id", "")
                    template_args = template.get("template_args", [])
                    payload = {
                        "channel": "whatsapp",
                        "type": "buttonTemplate",
                        "templateId": template_id,
                        "templateArgs": template_args,
                        "recipient": chat_id
                    }
                    return self.client.send_button_template(chat_id, template_id, template_args)
                else:
                    message = response_data.get("message", "Thank you for your message.")
                    # PATCH: Ensure only plain text is sent
                    if isinstance(message, dict):
                        message = message.get("message", "Thank you for your message.")
                    elif isinstance(message, (list, tuple)):
                        message = "\n".join(str(x) for x in message)
                    elif not isinstance(message, str):
                        message = str(message)
                    if message.strip().startswith("{") and message.strip().endswith("}"):
                        message = "Thank you for your message. I'm here to help you find products!"
                    return self.client.send_text(chat_id, message)
            else:
                message = response_data.get("message", "Thank you for your message.")
                # PATCH: Ensure only plain text is sent
                if isinstance(message, dict):
                    message = message.get("message", "Thank you for your message.")
                elif isinstance(message, (list, tuple)):
                    message = "\n".join(str(x) for x in message)
                elif not isinstance(message, str):
                    message = str(message)
                if message.strip().startswith("{") and message.strip().endswith("}"):
                    message = "Thank you for your message. I'm here to help you find products!"
                return self.client.send_text(chat_id, message)
        except Exception as e:
            logger.error(f"Failed to send WhatsApp response: {e}")
            return False

# Initialize services
conversation_manager = ConversationManager()
product_service = ProductService()
whatsapp_service = WhatsAppService()

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
    """Zoko webhook endpoint - handles both JSON and form data."""
    try:
        logger.info(f"📥 Zoko webhook received with token: {token}")
        
        # Try to get data from request body first (JSON)
        chat_id = None
        user_text = None
        customer_name = None
        direction = None
        event = None
        
        try:
            body = await request.json()
            logger.info(f"📥 Zoko webhook received JSON: {body}")
            
            # Extract data from JSON
            chat_id = body.get("platformSenderId") or body.get("chat_id") or body.get("sender")
            user_text = body.get("text") or body.get("message")
            customer_name = body.get("customerName") or body.get("customer_name")
            direction = body.get("direction")
            event = body.get("event")
            
        except Exception as json_error:
            logger.info(f"📥 Zoko webhook received form data: platformSenderId={platformSenderId}, text={text}")
            
            # Fallback to form data
            chat_id = platformSenderId
            user_text = text
            customer_name = customerName
        
        # CRITICAL FIX: Filter out outgoing messages from the bot to prevent infinite loop
        if direction == "FROM_STORE" or event == "message:store:out":
            logger.info(f"🚫 Ignoring outgoing message from bot: {direction} - {event}")
            return JSONResponse(content={"status": "ignored", "message": "Outgoing message from bot"})
        
        # Validate required fields
        if not chat_id:
            logger.error("Missing platformSenderId/chat_id in webhook payload")
            return JSONResponse(content={"status": "error", "message": "Missing chat_id"}, status_code=400)
        
        if not user_text:
            logger.info("No text in payload; likely a delivery or read event.")
            return JSONResponse(content={"status": "ignored", "message": "No text content"})
        
        # Process the message asynchronously
        background_tasks.add_task(process_zoko_message, {
            "platformSenderId": chat_id,
            "text": user_text,
            "customerName": customer_name,
            "platformTimestamp": platformTimestamp,
            "type": type,
            "id": id
        })
        
        logger.info(f"✅ Webhook accepted for {chat_id}: {user_text[:50]}...")
        return JSONResponse(content={"status": "accepted"})
        
    except Exception as e:
        logger.error(f"Zoko webhook error: {e}", exc_info=True)
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.post("/webhook/zoko/")
async def zoko_webhook_alt(request: Request, background_tasks: BackgroundTasks, token: Optional[str] = Query(None)):
    """Alternative Zoko webhook endpoint with trailing slash."""
    return await zoko_webhook(request, background_tasks, token)

async def process_zoko_message(payload: Dict):
    """Process Zoko webhook message asynchronously."""
    start_time = time.time()
    
    try:
        chat_id = payload.get("platformSenderId")
        user_text = payload.get("text")
        customer_name = payload.get("customerName")
        
        # Additional safety check to prevent bot message processing
        if not user_text or not user_text.strip():
            logger.info(f"🚫 Skipping empty message from {chat_id}")
            return
        
        # Check if this looks like a bot response (common bot phrases)
        bot_indicators = [
            "How can I assist you",
            "Please let me know",
            "I'll help you find",
            "Just let me know",
            "Are you looking for"
        ]
        
        if any(indicator.lower() in user_text.lower() for indicator in bot_indicators):
            logger.info(f"🚫 Skipping potential bot message: {user_text[:50]}...")
            return
        
        logger.info(f"🔄 Processing Zoko message from {customer_name} ({chat_id}): {user_text}")
        
        # 1. Save incoming user message
        conversation_manager.save_conversation(
            chat_id, "user", user_text, {"customer_name": customer_name, "source": "zoko_webhook"}
        )
        
        # 2. Get conversation history
        history = conversation_manager.get_conversation_history(chat_id, limit=5)
        logger.info(f"📖 Loaded {len(history)} previous messages for context")
        
        # 3. Get customer profile
        customer_profile = conversation_manager.get_customer_profile(chat_id)
        logger.info(f"👤 Customer profile: {customer_profile.get('interaction_count', 0)} interactions")
        
        # 4. Run the agent (TED)
        logger.info(f"🤖 Running agent with message: {user_text[:50]}...")
        response = await chat_with_agent_enhanced(user_text, user_lang="en", chat_id=chat_id)
        
        # 5. Save agent response
        conversation_manager.save_conversation(
            chat_id, "bot", response.get("message", "Agent response"),
            {
                "response_type": response.get("whatsapp_type", "text"),
                "products_count": len(response.get("products", [])),
                "template_used": response.get("template", {}).get("template_id") if response.get("template") else None
            }
        )
        
        # 6. Send rich WhatsApp response
        logger.info(f"📱 Sending WhatsApp response to {chat_id}")
        sent = whatsapp_service.send_rich_response(chat_id, response)
        
        if not sent:
            logger.error(f"❌ Failed to send WhatsApp message to {chat_id}")
            fallback_msg = "Thank you for your message. I'm here to help you find products!"
            zoko_client.send_text(chat_id, fallback_msg)
        
        # 7. Update customer profile
        if gcp_db:
            profile_ref = gcp_db.collection("customer_profiles").document(chat_id)
            profile_ref.set({
                "last_interaction": datetime.now().isoformat(),
                "interaction_count": customer_profile.get("interaction_count", 0) + 1,
                "last_query": user_text,
                "customer_name": customer_name,
                "preferences": customer_profile.get("preferences", {})
            }, merge=True)
        
        processing_time = time.time() - start_time
        logger.info(f"✅ Zoko message processed in {processing_time:.2f}s for {chat_id}")
        
    except Exception as e:
        logger.error(f"❌ Error processing Zoko message: {e}", exc_info=True)

@app.post("/ted/whatsapp")
async def ted_whatsapp_endpoint(
    request: Request,
    chat_id: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    customer_name: Optional[str] = Form(None),
    lang: Optional[str] = Form("en")
):
    """TED endpoint - accepts both JSON and form data."""
    start_time = time.time()
    
    try:
        # Try to get data from request body first (JSON)
        try:
            body = await request.json()
            logger.info(f"🚀 TED endpoint received JSON: {body}")
            
            msg = WhatsAppMessage(**body)
            chat_id = msg.chat_id
            text = msg.text
            customer_name = msg.customer_name
            lang = msg.lang
            
        except Exception as json_error:
            # Fallback to form data
            logger.info(f"🚀 TED endpoint received form data: chat_id={chat_id}, text={text}")
            
            if not chat_id or not text:
                raise HTTPException(status_code=400, detail="chat_id and text are required")
        
        logger.info(f"🚀 TED endpoint called by {chat_id}: {text}")
        
        # 1. Save incoming user message
        conversation_manager.save_conversation(chat_id, "user", text, {"customer_name": customer_name, "lang": lang})
        
        # 2. Get conversation history
        history = conversation_manager.get_conversation_history(chat_id, limit=5)
        logger.info(f"📖 Loaded {len(history)} previous messages for context")
        
        # 3. Get customer profile
        customer_profile = conversation_manager.get_customer_profile(chat_id)
        logger.info(f"👤 Customer profile: {customer_profile.get('interaction_count', 0)} interactions")
        
        # 4. Run the agent (TED)
        logger.info(f"🤖 Running agent with message: {text[:50]}...")
        response = await chat_with_agent_enhanced(text, user_lang=lang, chat_id=chat_id)
        
        # 5. Save agent response
        conversation_manager.save_conversation(
            chat_id, "bot", response.get("message", "Agent response"),
            {
                "response_type": response.get("whatsapp_type", "text"),
                "products_count": len(response.get("products", [])),
                "template_used": response.get("template", {}).get("template_id") if response.get("template") else None
            }
        )
        
        # 6. Send rich WhatsApp response
        logger.info(f"📱 Sending WhatsApp response to {chat_id}")
        sent = whatsapp_service.send_rich_response(chat_id, response)
        
        if not sent:
            logger.error(f"❌ Failed to send WhatsApp message to {chat_id}")
            raise HTTPException(status_code=500, detail="Failed to send WhatsApp message")
        
        # 7. Update customer profile
        if gcp_db:
            profile_ref = gcp_db.collection("customer_profiles").document(chat_id)
            profile_ref.set({
                "last_interaction": datetime.now().isoformat(),
                "interaction_count": customer_profile.get("interaction_count", 0) + 1,
                "last_query": text,
                "preferences": customer_profile.get("preferences", {})
            }, merge=True)
        
        processing_time = time.time() - start_time
        logger.info(f"✅ TED workflow completed in {processing_time:.2f}s for {chat_id}")
        
        return {
            "status": "success",
            "processing_time": processing_time,
            "agent_response": response,
            "conversation_saved": True,
            "whatsapp_sent": sent,
            "products_found": len(response.get("products", []))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ TED endpoint error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500, 
            content={"status": "error", "message": str(e), "processing_time": time.time() - start_time}
        )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        firebase_status = "connected" if gcp_db else "disconnected"
        zoko_status = "configured" if hasattr(zoko_client, 'api_key') and zoko_client.api_key else "not_configured"
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "firebase": firebase_status,
                "zoko": zoko_status,
                "openai": "configured" if settings.OPENAI_API_KEY else "not_configured"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(status_code=500, content={"status": "unhealthy", "error": str(e)})

@app.get("/conversation/{chat_id}")
async def get_conversation_history(chat_id: str, limit: int = 20):
    """Get conversation history for a chat ID."""
    try:
        history = conversation_manager.get_conversation_history(chat_id, limit)
        profile = conversation_manager.get_customer_profile(chat_id)
        
        return {
            "chat_id": chat_id,
            "history": history,
            "profile": profile,
            "message_count": len(history)
        }
    except Exception as e:
        logger.error(f"Failed to get conversation history for {chat_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search/products")
async def search_products_endpoint(query: str, limit: int = 10):
    """Direct product search endpoint."""
    try:
        result = product_service.search_products(query, limit)
        return result
    except Exception as e:
        logger.error(f"Product search endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sync/shopify-products")
async def sync_shopify_products():
    """
    Fetch products from Shopify and add only new products to Firestore.
    If a product already exists (by ID), it is skipped.
    """
    try:
        from src.products import get_product_by_id
        # You must implement this function to fetch products from Shopify
        from src.products import fetch_products_from_shopify
        
        shopify_products = fetch_products_from_shopify()
        if not shopify_products:
            return {"status": "error", "message": "No products fetched from Shopify."}
        
        added = 0
        skipped = 0
        for product in shopify_products:
            product_id = str(product.get("id"))
            if not product_id:
                continue
            existing = get_product_by_id(product_id)
            if existing:
                skipped += 1
                continue
            # Add to Firestore
            from src.products import add_products_to_firestore
            add_products_to_firestore([product])
            added += 1
        return {
            "status": "success",
            "added": added,
            "skipped": skipped,
            "total_fetched": len(shopify_products)
        }
    except Exception as e:
        logger.error(f"Failed to sync Shopify products: {e}")
        return {"status": "error", "message": str(e)}
