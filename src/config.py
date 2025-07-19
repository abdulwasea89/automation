import logging
import os

from dotenv import load_dotenv
from src.logger import get_logger

load_dotenv()

# Basic logging setup
logging.basicConfig(level=logging.INFO)
logger = get_logger("config")


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
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Performance settings
    ENABLE_IMAGE_VALIDATION: bool = os.getenv("ENABLE_IMAGE_VALIDATION", "false").lower() == "true"
    ENABLE_DETAILED_LOGGING: bool = os.getenv("ENABLE_DETAILED_LOGGING", "false").lower() == "true"
    MAX_DB_SCAN_LIMIT: int = int(os.getenv("MAX_DB_SCAN_LIMIT", "50"))
    MEMORY_SUMMARY_INTERVAL: int = int(os.getenv("MEMORY_SUMMARY_INTERVAL", "5"))

    def validate(self):
        # Only validate PROJECT_ID for now to allow deployment testing
        if not self.PROJECT_ID:
            logger.error("Missing environment variable: PROJECT_ID")
            raise ValueError("Missing environment variable: PROJECT_ID")
        
        # Log warnings for missing optional variables instead of failing
        optional_vars = [
            "OPENAI_API_KEY",
            "SHOPIFY_API_KEY", 
            "SHOPIFY_API_PASSWORD",
            "SHOPIFY_STORE_NAME",
            "ZOKO_API_KEY",
            "ZOKO_API_URL"
        ]
        
        for key in optional_vars:
            if not getattr(self, key):
                logger.warning(f"Missing optional environment variable: {key}")


settings = Settings()
settings.validate()
