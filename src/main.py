import os
import json
import asyncio
from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
from src.logger import get_logger
from src.openai_agent import chat_with_agent_enhanced
from src.zoko_client import zoko_client
from collections import OrderedDict
from time import time
from typing import Dict
import re

logger = get_logger("app")
app = FastAPI(title="LEVA ASSISTANT")

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

class WhatsAppMessage(BaseModel):
    chat_id: str
    text: str
    customer_name: str = None
    lang: str = "en"

@app.post("/webhook/zoko")
async def zoko_webhook(request: Request, background_tasks: BackgroundTasks):
    """Zoko webhook endpoint."""
    try:
        body = await request.json()
        logger.info(f"Webhook payload: {json.dumps(body, indent=2)}")
        # Skip non-user messages (e.g., delivery updates)
        event = body.get("event")
        if event != "message:user:in":
            logger.info(f"Skipping non-user event: {event}")
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
        if not chat_id or not user_text or not message_id:
            logger.error(f"Invalid webhook payload: missing chat_id, text, or id - {body}")
            return {"status": "error", "message": "Missing chat_id, text, or id"}
        
        # Skip bot-generated or duplicate messages
        if (body.get("direction") != "FROM_CUSTOMER" or 
            user_text.startswith("I'm having trouble processing your request") or 
            user_text.startswith("Hello! 👋") or 
            deduplicator.is_duplicate(message_id)):
            logger.info(f"Skipping bot-generated or duplicate message: {user_text[:50]} (ID: {message_id})")
            return {"status": "skipped", "message": "Bot or duplicate message ignored"}
        
        background_tasks.add_task(process_zoko_message, {
            "platformSenderId": chat_id,
            "text": user_text,
            "message_id": message_id
        })
        return {"status": "accepted"}
    except Exception as e:
        logger.error(f"Zoko webhook error: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def process_zoko_message(payload: Dict):
    """Process Zoko webhook message."""
    try:
        chat_id = payload["platformSenderId"]
        user_text = payload["text"]
        message_id = payload["message_id"]
        logger.info(f"Processing user message: {user_text} from {chat_id} (ID: {message_id})")

        # Log the payload for debugging
        logger.info(f"Received payload for selection: {user_text}")

        response = await chat_with_agent_enhanced(user_text, chat_id=chat_id)
        # Ensure response is always a dict
        if isinstance(response, str):
            logger.error(f"Agent returned a string instead of dict: {response}")
            response = {
                "success": False,
                "message": response,
                "whatsapp_type": "text"
            }
        # Skip sending response if flagged
        if response.get("skip_response"):
            logger.info(f"Skipping response for chat_id {chat_id} to prevent loop")
            return
        if response.get("whatsapp_type") == "text":
            zoko_client.send_text(chat_id, response.get("message", "I'm here to help!"))
        elif response.get("whatsapp_type") == "buttonTemplate":
            if "template_id" in response and "template_args" in response:
                zoko_client.send_button_template(chat_id, response["template_id"], response["template_args"])
            else:
                logger.error(f"Button template response missing keys: {response}")
                zoko_client.send_text(chat_id, response.get("message", "Sorry, something went wrong."))
        elif response.get("whatsapp_type") == "interactive_list":
            # Fallback: If response is flat, wrap into correct structure
            if "interactiveList" not in response and "items" in response:
                logger.warning("Fixing flat interactive list to expected structure")
                response["interactiveList"] = {
                    "list": {
                        "title": response.get("header", "Menu"),
                        "sections": [{
                            "title": "Options",
                            "items": response["items"]
                        }]
                    },
                    "body": {
                        "text": response.get("body", "Choose one:")
                    }
                }
            interactive = response.get("interactiveList")
            if interactive and "list" in interactive:
                list_obj = interactive["list"]
                sections = list_obj.get("sections", [])
                # Flatten and sanitize items from all sections
                def clean_text(text, maxlen):
                    text = re.sub(r'<[^>]+>', '', str(text))
                    text = re.sub(r'\s+', ' ', text)
                    t = text.strip()
                    if not t:
                        return "No description available"
                    if len(t) > maxlen:
                        return t[:maxlen-3] + '...'
                    return t
                items = []
                for section in sections:
                    for item in section.get("items", []):
                        desc = clean_text(item.get("description", ""), 50)
                        items.append({
                            "id": str(item.get("id", "")),
                            "payload": str(item.get("payload", "")),
                            "title": clean_text(item.get("title", ""), 24),
                            "description": desc
                        })
                # Ensure all items have a non-empty description
                for item in items:
                    if not item.get("description"):
                        item["description"] = "No description available"
                body = interactive["body"].get("text", "Choose an option:") if "body" in interactive else "Choose an option:"
                zoko_client.send_interactive_list(chat_id, list_obj.get("title", "LEVA Houses"), body, items)
            else:
                logger.error(f"Interactive list response missing 'interactiveList' or 'list': {response}")
                zoko_client.send_text(chat_id, response.get("message", "Sorry, something went wrong."))
    except Exception as e:
        logger.error(f"Error processing Zoko message (ID: {payload.get('message_id')}): {e}", exc_info=True)
        zoko_client.send_text(chat_id, "Sorry, something went wrong.")

@app.get("/")
def hello():
    return {
        "app is good"
    }