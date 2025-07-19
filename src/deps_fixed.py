import os

from google.cloud import firestore, storage

from src.config import settings
from src.logger import get_logger

logger = get_logger("deps")

# Try multiple credential paths
credentials_paths = [
    os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    # "./service-account.json",
    # "/app/service-account.json",
    os.path.join(
        os.path.dirname(
            os.path.dirname(__file__)),
        "service-account.json")]

credentials_path = None
for path in credentials_paths:
    if path and os.path.isfile(path):
        credentials_path = path
        break

if credentials_path:
    logger.info(f"Using credentials from: {credentials_path}")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(
        credentials_path)
else:
    logger.warning(
        "No service account file found in any of the expected locations")
    # logger.warning(
    #     "Expected locations: GOOGLE_APPLICATION_CREDENTIALS env var, ./service-account.json, /app/service-account.json")

try:
    if settings.PROJECT_ID:
        # Try to initialize with credentials
        if credentials_path:
            db = firestore.Client(project=settings.PROJECT_ID)
            bucket = storage.Client(
                project=settings.PROJECT_ID).bucket("zoko-ai-media")
        else:
            # Try with default credentials
            db = firestore.Client(
                project=settings.PROJECT_ID,
                credentials=None)
            bucket = storage.Client(
                project=settings.PROJECT_ID,
                credentials=None).bucket("zoko-ai-media")

        logger.info(f"Connected to GCP project: {settings.PROJECT_ID}")

        # Test the connection
        try:
            test_ref = db.collection("products").limit(1).stream()
            list(test_ref)  # This will actually test the connection
            logger.info("Database connection test successful")
        except Exception as test_error:
            logger.error(f"Database connection test failed: {test_error}")
            db = None
            bucket = None

    else:
        logger.warning("PROJECT_ID not set.")
        db = None
        bucket = None
except Exception as e:
    logger.error(f"GCP client init failed: {str(e)}")
    db = None
    bucket = None
