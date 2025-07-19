import json
import logging
import os
from datetime import datetime
from typing import Dict

from agents import MaxTurnsExceeded, Runner
from dotenv import load_dotenv

from db_agent import db_agent
from src.logger import get_logger
from src.openai_agent import chat_with_agent_enhanced

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = get_logger("agent_runner")


async def run_main_agent(
    user_message: str,
    user_lang: str = "en",
    chat_id: str = None
) -> Dict:
    """
    Run the main agent following official OpenAI Agents SDK patterns.

    Args:
        user_message: User's message
        user_lang: User's language preference
        chat_id: Chat ID for memory context

    Returns:
        Dict with agent response and metadata
    """
    logger.info(f"🤖 Main agent processing: {user_message[:100]}...")

    try:
        # Add context information
        context_msg = f"[Language: {user_lang}] {user_message}"
        if chat_id:
            context_msg += f" [ChatID: {chat_id}]"

        # Run the agent directly using the enhanced function
        result = await chat_with_agent_enhanced(context_msg, chat_id)

        # Parse the response
        try:
            if isinstance(result, dict):
                # Add agent metadata
                result["agent_info"] = {
                    "agent_name": "main_agent",
                    "handoff_occurred": False,
                    "timestamp": datetime.now().isoformat(),
                    "chat_id": chat_id}
                logger.info("✅ Main agent completed successfully")
                return result
        except (TypeError, AttributeError):
            pass

        # Fallback to plain text
        return {
            "message": str(result),
            "whatsapp_type": "text",
            "agent_info": {
                "agent_name": "main_agent",
                "handoff_occurred": False,
                "timestamp": datetime.now().isoformat(),
                "chat_id": chat_id
            }
        }

    except MaxTurnsExceeded:
        logger.warning("Main agent exceeded maximum turns")
        fallback_response = {
            "message": "I'm having trouble processing that request. "
                       "Let me transfer you to a specialist.",
            "whatsapp_type": "text",
            "agent_info": {
                "agent_name": "fallback",
                "handoff_occurred": True,
                "reason": "max_turns_exceeded",
                "timestamp": datetime.now().isoformat(),
                "chat_id": chat_id
            }
        }
        return fallback_response

    except Exception as e:
        logger.error(f"❌ Main agent error: {str(e)}", exc_info=True)
        fallback_response = {
            "message": "Sorry, I'm experiencing technical difficulties. "
                       "Please try again in a moment.",
            "whatsapp_type": "text",
            "agent_info": {
                "agent_name": "fallback",
                "handoff_occurred": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "chat_id": chat_id
            }
        }
        return fallback_response


async def run_database_agent(
    user_message: str,
    chat_id: str = None
) -> Dict:
    """
    Run only the database agent following official SDK patterns.

    Args:
        user_message: User's message
        chat_id: Chat ID for context

    Returns:
        Dict with database agent response
    """
    logger.info(f"🗄️ Database agent processing: {user_message[:100]}...")

    try:
        # Run the database agent directly
        result = await Runner.run(db_agent, user_message)

        # Parse the response
        try:
            response_data = json.loads(result.final_output)
            if isinstance(response_data, dict):
                response_data["agent_info"] = {
                    "agent_name": "database_agent",
                    "handoff_occurred": False,
                    "timestamp": datetime.now().isoformat(),
                    "chat_id": chat_id
                }
                logger.info("✅ Database agent completed successfully")
                return response_data
        except (json.JSONDecodeError, TypeError):
            pass

        # Fallback to plain text
        return {
            "message": result.final_output,
            "whatsapp_type": "text",
            "agent_info": {
                "agent_name": "database_agent",
                "handoff_occurred": False,
                "timestamp": datetime.now().isoformat(),
                "chat_id": chat_id
            }
        }

    except Exception as e:
        logger.error(f"❌ Database agent error: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": "Sorry, I'm having trouble with the database right now.",
            "whatsapp_type": "text",
            "error": str(e),
            "agent_info": {
                "agent_name": "database_agent",
                "handoff_occurred": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
                "chat_id": chat_id}}


def get_agent_mode(user_message: str) -> str:
    """
    Determine the best agent mode based on user message.

    Args:
        user_message: User's message

    Returns:
        Agent mode: "main", "database", "orchestrated"
    """
    message_lower = user_message.lower()

    # Database-specific keywords
    db_keywords = [
        "search", "find", "property", "properties", "database", "query",
        "filter", "criteria", "details", "browse", "list", "show"
    ]

    # General conversation keywords
    general_keywords = [
        "hello", "hi", "help", "thanks", "thank you", "goodbye", "bye",
        "how are you", "what can you do", "introduction"
    ]

    # Count matches
    db_matches = sum(1 for keyword in db_keywords if keyword in message_lower)
    general_matches = sum(
        1 for keyword in general_keywords if keyword in message_lower
    )

    if db_matches > 2:
        return "database"
    elif general_matches > 0 and db_matches == 0:
        return "main"
    else:
        return "orchestrated"


async def smart_agent_routing(
    user_message: str,
    user_lang: str = "en",
    chat_id: str = None
) -> Dict:
    """
    Smart routing to the most appropriate agent following official SDK patterns.

    Args:
        user_message: User's message
        user_lang: User's language preference
        chat_id: Chat ID for context

    Returns:
        Dict with agent response
    """
    mode = get_agent_mode(user_message)
    logger.info(f"🧠 Smart routing mode: {mode}")

    if mode == "database":
        return await run_database_agent(user_message, chat_id)
    elif mode == "main":
        return await run_main_agent(user_message, user_lang, chat_id)
    else:
        # Use main agent which has handoffs configured
        return await run_main_agent(user_message, user_lang, chat_id)
