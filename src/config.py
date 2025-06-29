import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Basic logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("config")

class Settings:
    """Application configuration."""
    PROJECT_ID: str = os.getenv("PROJECT_ID", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    SHOPIFY_API_KEY: str = os.getenv("SHOPIFY_API_KEY", "")
    SHOPIFY_API_PASSWORD: str = os.getenv("SHOPIFY_API_PASSWORD", "")
    SHOPIFY_STORE_NAME: str = os.getenv("SHOPIFY_STORE_NAME", "")
    ZOKO_API_KEY: str = os.getenv("ZOKO_API_KEY", "")
    ZOKO_API_URL = os.getenv("ZOKO_API_URL")
    CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
    RATE_LIMIT = int(os.getenv("RATE_LIMIT", "30"))
    RATE_PERIOD = int(os.getenv("RATE_PERIOD", "60"))

    def validate(self):
        required = [
            "PROJECT_ID", "OPENAI_API_KEY", "SHOPIFY_API_KEY", 
            "SHOPIFY_API_PASSWORD", "SHOPIFY_STORE_NAME", "ZOKO_API_KEY","ZOKO_API_URL","CACHE_TTL","RATE_LIMIT","RATE_PERIOD"
        ]
        for key in required:
            if not getattr(self, key):
                logger.error(f"Missing environment variable: {key}")
                raise ValueError(f"Missing environment variable: {key}")

settings = Settings()
settings.validate()