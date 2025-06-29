import os
import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from dotenv import load_dotenv
from agents import Runner, Agent
from agents.tracing import trace
from agents import MaxTurnsExceeded
from src.logger import get_logger
from src.openai_agent import agent as main_agent
from src.db_agent import db_agent

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
        
        # Run the agent with tracing following official SDK patterns
        with trace(workflow_name="whatsapp_property_chat", group_id=os.getenv("ZOKO_CHANNEL_ID", "")):
            result = await Runner.run(main_agent, context_msg)
        
        # Parse the response
        try:
            response_data = json.loads(result.final_output)
            if isinstance(response_data, dict):
                # Add agent metadata
                response_data["agent_info"] = {
                    "agent_name": result.agent.name if hasattr(result, 'agent') else "main_agent",
                    "handoff_occurred": result.agent.name == "database_agent" if hasattr(result, 'agent') else False,
                    "timestamp": datetime.now().isoformat(),
                    "chat_id": chat_id
                }
                logger.info(f"✅ Main agent completed successfully")
                return response_data
        except (json.JSONDecodeError, TypeError):
            pass
        
        # Fallback to plain text
        return {
            "message": result.final_output,
            "whatsapp_type": "text",
            "agent_info": {
                "agent_name": result.agent.name if hasattr(result, 'agent') else "main_agent",
                "handoff_occurred": False,
                "timestamp": datetime.now().isoformat(),
                "chat_id": chat_id
            }
        }
        
    except MaxTurnsExceeded:
        logger.warning("Main agent exceeded maximum turns")
        fallback_response = {
            "message": "I'm having trouble processing that request. Let me transfer you to a specialist.",
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
            "message": "Sorry, I'm experiencing technical difficulties. Please try again in a moment.",
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
        # Run the database agent with tracing
        with trace(workflow_name="database_operations", group_id=os.getenv("ZOKO_CHANNEL_ID", "")):
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
                logger.info(f"✅ Database agent completed successfully")
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
                "chat_id": chat_id
            }
        }

# Utility functions for different routing modes
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
    general_matches = sum(1 for keyword in general_keywords if keyword in message_lower)
    
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

# Example usage following official SDK patterns
async def example_usage():
    """
    Example usage following the official OpenAI Agents SDK documentation.
    """
    # Example 1: Simple conversation
    result1 = await run_main_agent("Hello, how are you?", chat_id="user123")
    print(f"Main agent response: {result1.get('message', 'N/A')}")
    
    # Example 2: Database operation
    result2 = await run_database_agent("Search for 3 bedroom apartments", chat_id="user123")
    print(f"Database agent response: {result2.get('success', 'N/A')}")
    
    # Example 3: Smart routing
    result3 = await smart_agent_routing("Find properties with pool", chat_id="user123")
    print(f"Smart routing response: {result3.get('agent_info', {}).get('agent_name', 'N/A')}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage()) 