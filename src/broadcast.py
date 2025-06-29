import json
from src.deps import db
from src.zoko_client import send_text
from src.logger import get_logger

# Initialize logger for this module
logger = get_logger("broadcast")

# Load message templates from templates.json, fallback to default if error occurs
try:
    with open("./templates.json") as f:
        TEMPLATES = json.load(f)
    # Ensure the 'promo' key exists and is a dictionary
    if not isinstance(TEMPLATES.get("promo"), dict):
        raise ValueError("Invalid templates.json: 'promo' must be a dictionary")
except Exception as e:
    logger.error(f"Failed to load templates.json: {str(e)}")
    # Fallback to a default template if loading fails
    TEMPLATES = {"promo": {"en": "Hello {name}, check out our latest offers!"}}

def get_all_users() -> list[dict]:
    """
    Fetch all user sessions from Firestore.

    Returns:
        List of user session dictionaries, each containing at least 'chat_id'.
        Returns an empty list if Firestore is unavailable or an error occurs.
    """
    if db is None:
        logger.warning("GCP not available, returning empty user list")
        return []
    
    try:
        # Stream all documents from the 'sessions' collection
        users = [{"chat_id": d.id, **d.to_dict()} for d in db.collection("sessions").stream()]
        logger.info(f"Fetched {len(users)} users for broadcast")
        return users
    except Exception as e:
        logger.error(f"Failed to fetch users: {str(e)}")
        return []

def broadcast_promo():
    """
    Send promotional messages to all users.

    For each user, selects the appropriate language template and sends a personalized message.
    Logs success or failure for each user.
    """
    users = get_all_users()
    if not users:
        logger.warning("No users found for broadcast")
        return
    
    for u in users:
        # Get user's name or fallback to chat_id
        name = u.get("name", u["chat_id"])
        # Get user's preferred language or default to English
        lang = u.get("language", "en")
        # Select the template for the user's language, fallback to English if not found
        text = TEMPLATES["promo"].get(lang, TEMPLATES["promo"]["en"]).format(name=name)
        try:
            # Send the promotional text to the user
            send_text(u["chat_id"], text)
            logger.info(f"Sent promo to {u['chat_id']} in {lang}")
        except Exception as e:
            logger.error(f"Failed to send promo to {u['chat_id']}: {str(e)}")