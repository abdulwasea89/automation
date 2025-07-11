# ✅ shopify_client.py
import os
import json
import logging
from typing import List, Dict, Any
import requests
from requests.auth import HTTPBasicAuth
from src.config import settings

logger = logging.getLogger("shopify_client")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

API_VERSION = "2024-04"
BASE_URL = f"https://{settings.SHOPIFY_STORE_NAME}.myshopify.com/admin/api/{API_VERSION}"
AUTH = HTTPBasicAuth(settings.SHOPIFY_API_KEY, settings.SHOPIFY_API_PASSWORD)

# Shopify API max limit is 100 per request
MAX_SHOPIFY_LIMIT = 100

def get_all_products(limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch all products from Shopify as dicts. Limit capped to 100 per Shopify API."""
    limit = min(limit, MAX_SHOPIFY_LIMIT)
    logger.info(f"Using store: {settings.SHOPIFY_STORE_NAME}, key: {settings.SHOPIFY_API_KEY[:4]}..., pass: {settings.SHOPIFY_API_PASSWORD[:4]}...")
    url = f"{BASE_URL}/products.json?limit={limit}"
    try:
        logger.info(f"Fetching products from Shopify with limit={limit} via HTTP...")
        resp = requests.get(url, auth=AUTH)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Raw products HTTP response: {data}")
        products = data.get("products", [])
        logger.info(f"Products list: {products}")
        return products
    except Exception as e:
        logger.error("Failed to fetch products", exc_info=True)
        return []

def get_product_by_id(product_id: int) -> Dict[str, Any]:
    """Fetch a single product by ID."""
    url = f"{BASE_URL}/products/{product_id}.json"
    try:
        resp = requests.get(url, auth=AUTH)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Raw product by ID HTTP response: {data}")
        return data.get("product", {})
    except Exception as e:
        logger.error("Failed to fetch product by ID", exc_info=True)
        return {}

def search_products_by_keywords(query: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Search products by keywords. Limit capped to 100 per Shopify API."""
    limit = min(limit, MAX_SHOPIFY_LIMIT)
    url = f"{BASE_URL}/products.json?limit={limit}"
    try:
        resp = requests.get(url, auth=AUTH)
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Raw products HTTP response for search: {data}")
        products = data.get("products", [])
        query = query.lower()
        matches = [ 
            p for p in products
            if any(
                word in (f"{p.get('title', '')} {p.get('body_html', '')} {' '.join(p.get('tags', '').split())}").lower()
                for word in query.split() if len(word) > 2
            )
        ]
        return matches
    except Exception as e:
        logger.error("Failed to search products", exc_info=True)
        return []

def save_products_to_file(filename: str = "products.json") -> bool:
    """Save all products to a JSON file."""
    try:
        products = get_all_products()
        with open(filename, "w") as f:
            json.dump(products, f, indent=2)
        logger.info(f"Saved {len(products)} products to {filename}")
        return True
    except Exception as e:
        logger.error("Failed to save products", exc_info=True)
        return False