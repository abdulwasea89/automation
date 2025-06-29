import time
from typing import List, Dict
from src.deps import db
from google.cloud import firestore
from src.logger import get_logger

logger = get_logger("gcp")

class ChatMemory:
    COLLECTION = "sessions"
    MESSAGES_FIELD = "messages"

    @staticmethod
    def save_message(chat_id: str, role: str, msg: str) -> None:
        if db is None:
            logger.warning("GCP not available, message not saved")
            return
        if not isinstance(msg, str) or not msg.strip():
            logger.error(f"Invalid or empty message for {chat_id}: {msg!r}")
            return
        role = role.lower()
        if role not in ("user", "bot"):
            logger.warning(f"Unknown role '{role}' for {chat_id}, saving as 'user'")
            role = "user"
        record = {"role": role, "msg": msg, "time": time.time()}
        ref = db.collection(ChatMemory.COLLECTION).document(chat_id)
        try:
            ref.set({ChatMemory.MESSAGES_FIELD: []}, merge=True)
            ref.update({ChatMemory.MESSAGES_FIELD: firestore.ArrayUnion([record])})
            logger.info(f"Saved message for {chat_id} as {role}")
        except Exception as e:
            logger.error(f"Failed to save message for {chat_id}: {str(e)}")

    @staticmethod
    def load_history(chat_id: str) -> List[Dict]:
        if db is None:
            logger.warning("GCP not available, returning empty history")
            return []
        try:
            doc = db.collection(ChatMemory.COLLECTION).document(chat_id).get()
            messages = doc.to_dict().get(ChatMemory.MESSAGES_FIELD, []) if doc.exists else []
            valid_messages = [
                msg for msg in messages
                if isinstance(msg, dict)
                and msg.get("role") in ("user", "bot")
                and isinstance(msg.get("msg"), str)
                and isinstance(msg.get("time"), (int, float))
            ]
            logger.info(f"Loaded {len(valid_messages)} valid messages for {chat_id}")
            if len(valid_messages) < len(messages):
                logger.warning(f"Filtered out {len(messages) - len(valid_messages)} invalid messages for {chat_id}")
            return valid_messages
        except Exception as e:
            logger.error(f"Failed to load history for {chat_id}: {str(e)}")
            return []

    @staticmethod
    def clear_history(chat_id: str) -> None:
        if db is None:
            logger.warning("GCP not available, cannot clear history")
            return
        try:
            ref = db.collection(ChatMemory.COLLECTION).document(chat_id)
            ref.set({ChatMemory.MESSAGES_FIELD: []}, merge=True)
            logger.info(f"Cleared chat history for {chat_id}")
        except Exception as e:
            logger.error(f"Failed to clear history for {chat_id}: {str(e)}")

save_message = ChatMemory.save_message
load_history = ChatMemory.load_history