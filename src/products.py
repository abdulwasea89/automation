import os
import json
import time
from typing import List, Dict, Optional, Any
from google.cloud import firestore
from src.deps import db
from src.logger import get_logger

logger = get_logger("products")

PRODUCTS_COLLECTION = "products"
PRODUCTS_JSON_PATH = "./products.json"

def load_products_from_json() -> List[Dict[str, Any]]:
    """
    Load product data from the root-level products.json file.

    Returns:
        List[Dict[str, Any]]: List of product dictionaries.
    """
    try:
        if not os.path.exists(PRODUCTS_JSON_PATH):
            logger.error(f"Products file not found: {PRODUCTS_JSON_PATH}")
            return []
            
        with open(PRODUCTS_JSON_PATH, "r", encoding="utf-8") as f:
            products = json.load(f)
        
        if not isinstance(products, list):
            logger.error(f"Invalid JSON format: expected list, got {type(products)}")
            return []
            
        logger.info(f"Loaded {len(products)} products from {PRODUCTS_JSON_PATH}")
        return products
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from {PRODUCTS_JSON_PATH}: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Failed to load products from {PRODUCTS_JSON_PATH}: {str(e)}")
        return []

def validate_product(product: Dict[str, Any]) -> bool:
    """
    Validate a product dictionary has required fields.

    Args:
        product (Dict[str, Any]): Product dictionary to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ["title", "vendor"]
    for field in required_fields:
        if field not in product or not product[field]:
            logger.warning(f"Product missing required field: {field}")
            return False
    return True

def add_products_to_firestore(products: List[Dict[str, Any]], batch_size: int = 500) -> None:
    """
    Add a list of products to the Firestore 'products' collection using batch operations.

    Args:
        products (List[Dict[str, Any]]): List of product dictionaries to add.
        batch_size (int): Number of products to process in each batch.

    Returns:
        None
    """
    if db is None:
        logger.error("Firestore client not available. Check GCP credentials and PROJECT_ID.")
        return

    if not products:
        logger.warning("No products to add to Firestore")
        return

    # Filter out invalid products
    valid_products = [p for p in products if validate_product(p)]
    if len(valid_products) != len(products):
        logger.warning(f"Filtered out {len(products) - len(valid_products)} invalid products")

    if not valid_products:
        logger.error("No valid products to add")
        return

    total_products = len(valid_products)
    successful = 0
    failed = 0

    # Process products in batches
    for i in range(0, total_products, batch_size):
        batch = valid_products[i:i + batch_size]
        batch_ref = db.batch()
        
        for product in batch:
            try:
                # Use product ID as document ID if available, otherwise auto-generate
                doc_id = str(product.get("id")) if product.get("id") else None
                
                # Add timestamp for tracking
                product["imported_at"] = firestore.SERVER_TIMESTAMP
                product["last_updated"] = firestore.SERVER_TIMESTAMP
                
                if doc_id:
                    doc_ref = db.collection(PRODUCTS_COLLECTION).document(doc_id)
                    batch_ref.set(doc_ref, product, merge=True)
                else:
                    doc_ref = db.collection(PRODUCTS_COLLECTION).document()
                    batch_ref.set(doc_ref, product)
                    
            except Exception as e:
                logger.error(f"Failed to prepare product {product.get('id', 'unknown')}: {str(e)}")
                failed += 1
                continue

        # Commit the batch
        try:
            batch_ref.commit()
            successful += len(batch)
            logger.info(f"Successfully added batch of {len(batch)} products to Firestore")
        except Exception as e:
            logger.error(f"Failed to commit batch: {str(e)}")
            failed += len(batch)

    logger.info(f"Import completed: {successful} successful, {failed} failed out of {total_products} total")

def get_product_by_id(product_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a product from Firestore by ID.
    
    Args:
        product_id (str): The product ID to retrieve
        
    Returns:
        Optional[Dict[str, Any]]: Product data if found, None otherwise
    """
    if db is None:
        logger.error("Firestore client not available")
        return None
        
    try:
        doc = db.collection(PRODUCTS_COLLECTION).document(product_id).get()
        if doc.exists:
            return doc.to_dict()
        else:
            logger.info(f"Product with ID {product_id} not found")
            return None
    except Exception as e:
        logger.error(f"Failed to retrieve product {product_id}: {str(e)}")
        return None

def search_products(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search products by title or vendor.
    
    Args:
        query (str): Search query
        limit (int): Maximum number of results
        
    Returns:
        List[Dict[str, Any]]: List of matching products
    """
    if db is None:
        logger.error("Firestore client not available")
        return []
        
    try:
        # Search in title field
        title_query = db.collection(PRODUCTS_COLLECTION).where("title", ">=", query).where("title", "<=", query + "\uf8ff").limit(limit)
        title_results = [doc.to_dict() for doc in title_query.stream()]
        
        # Search in vendor field
        vendor_query = db.collection(PRODUCTS_COLLECTION).where("vendor", ">=", query).where("vendor", "<=", query + "\uf8ff").limit(limit)
        vendor_results = [doc.to_dict() for doc in vendor_query.stream()]
        
        # Combine and deduplicate results
        all_results = title_results + vendor_results
        seen_ids = set()
        unique_results = []
        
        for product in all_results:
            product_id = product.get("id")
            if product_id and product_id not in seen_ids:
                seen_ids.add(product_id)
                unique_results.append(product)
                
        logger.info(f"Found {len(unique_results)} products matching query: {query}")
        return unique_results[:limit]
        
    except Exception as e:
        logger.error(f"Failed to search products: {str(e)}")
        return []

def delete_product(product_id: str) -> bool:
    """
    Delete a product from Firestore.
    
    Args:
        product_id (str): The product ID to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    if db is None:
        logger.error("Firestore client not available")
        return False
        
    try:
        db.collection(PRODUCTS_COLLECTION).document(product_id).delete()
        logger.info(f"Successfully deleted product {product_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete product {product_id}: {str(e)}")
        return False

def get_all_products_from_firestore(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Retrieve all products from Firestore.
    
    Args:
        limit (int): Maximum number of products to retrieve
        
    Returns:
        List[Dict[str, Any]]: List of products
    """
    if db is None:
        logger.error("Firestore client not available")
        return []
        
    try:
        docs = db.collection(PRODUCTS_COLLECTION).limit(limit).stream()
        products = [doc.to_dict() for doc in docs]
        logger.info(f"Retrieved {len(products)} products from Firestore")
        return products
    except Exception as e:
        logger.error(f"Failed to retrieve products from Firestore: {str(e)}")
        return []

def import_products() -> None:
    """
    Import products from the root-level products.json file into the Firestore 'products' collection.

    Returns:
        None
    """
    logger.info("Starting product import process...")
    
    # Check if Firestore is available
    if db is None:
        logger.error("Cannot import products: Firestore client not available")
        logger.error("Please ensure:")
        logger.error("1. GOOGLE_APPLICATION_CREDENTIALS environment variable is set")
        logger.error("2. PROJECT_ID environment variable is set")
        logger.error("3. Service account has Firestore permissions")
        return
    
    # Load products from JSON
    products = load_products_from_json()
    if not products:
        logger.error("No products found to import")
        return
    
    # Add products to Firestore
        add_products_to_firestore(products)
    logger.info("Product import process completed")

def export_products_to_json(output_path: str = "./exported_products.json") -> bool:
    """
    Export all products from Firestore to a JSON file.
    
    Args:
        output_path (str): Path to save the exported JSON file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        products = get_all_products_from_firestore(limit=1000)
        if not products:
            logger.warning("No products found to export")
            return False
            
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2, ensure_ascii=False, default=str)
            
        logger.info(f"Successfully exported {len(products)} products to {output_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to export products: {str(e)}")
        return False

if __name__ == "__main__":
    import_products()
