import os
import time
from google.cloud import firestore, storage
from src.config import settings
from src.logger import get_logger

logger = get_logger("deps")

# Connection cache
_connection_cache = {}
_cache_timestamp = 0
_cache_ttl = 300  # 5 minutes

def get_db_connection():
    """Get cached database connection with TTL."""
    global _connection_cache, _cache_timestamp
    
    current_time = time.time()
    
    # Return cached connection if still valid
    if current_time - _cache_timestamp < _cache_ttl and 'db' in _connection_cache:
        return _connection_cache['db'], _connection_cache.get('bucket')
    
    # Initialize new connection
    try:
        if settings.PROJECT_ID:
            # Try to initialize with credentials
            credentials_path = None
            credentials_paths = [
                os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
                './service-account.json',
                '/app/service-account.json',
                os.path.join(os.path.dirname(os.path.dirname(__file__)), 'service-account.json')
            ]
            for path in credentials_paths:
                if path and os.path.isfile(path):
                    credentials_path = path
                    break
            if credentials_path:
                logger.info(f"Using credentials from: {credentials_path}")
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(credentials_path)
                db = firestore.Client(project=settings.PROJECT_ID)
                bucket = storage.Client(project=settings.PROJECT_ID).bucket("zoko-ai-media")
            else:
                logger.warning("No service account file found, using default credentials")
                db = firestore.Client(project=settings.PROJECT_ID, credentials=None)
                bucket = storage.Client(project=settings.PROJECT_ID, credentials=None).bucket("zoko-ai-media")
            # Cache the connection
            _connection_cache = {'db': db, 'bucket': bucket}
            _cache_timestamp = current_time
            logger.info(f"Connected to GCP project: {settings.PROJECT_ID}")
            return db, bucket
        else:
            logger.warning("PROJECT_ID not set.")
            return None, None
    except Exception as e:
        logger.error(f"GCP client init failed: {str(e)}")
        return None, None

# Initialize connection
db, bucket = get_db_connection()
