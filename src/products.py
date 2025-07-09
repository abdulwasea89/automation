import os
import json
import time
import re
from typing import List, Dict, Optional, Any
from google.cloud import firestore
from src.deps import db
from src.logger import get_logger
from fuzzywuzzy import fuzz
from rapidfuzz import process as rapidfuzz_process

logger = get_logger("products")

PRODUCTS_COLLECTION = "products"
PRODUCTS_JSON_PATH = "./products.json"

CATEGORY_KEYWORDS = {
    "house": [
        "house", "home", "villa", "residence", "dwelling", "cottage", "bungalow", "mansion", "estate", "chalet", "manor", "farmhouse", "ranch", "cabin", "homestead", "domicile", "abode", "lodging", "quarters", "habitation", "retreat", "residence", "family house", "detached house", "semi-detached", "row house", "terraced house", "country house", "urban house", "modern house", "classic house", "colonial house", "luxury house", "eco house", "smart home", "tiny house", "prefab house", "modular house", "container house", "timber house", "stone house", "brick house", "contemporary house", "traditional house", "split-level house", "duplex", "triplex", "quadplex", "multi-family house", "single-family house", "starter home", "dream home"
    ],
    "apartment": [
        "apartment", "flat", "studio", "loft", "condo", "condominium", "penthouse", "suite", "duplex apartment", "triplex apartment", "micro-apartment", "serviced apartment", "furnished apartment", "unfurnished apartment", "rental apartment", "luxury apartment", "student apartment", "shared apartment", "co-living", "apartment unit", "apartment building", "apartment complex", "high-rise apartment", "low-rise apartment", "mid-rise apartment", "garden apartment", "walk-up apartment", "basement apartment", "attic apartment", "efficiency apartment", "one-bedroom", "two-bedroom", "three-bedroom", "four-bedroom", "studio flat", "bachelor apartment", "apartment suite", "apartment home", "city apartment", "urban apartment", "suburban apartment", "apartment rental", "apartment for sale", "apartment lease", "apartment share", "apartment block", "apartment tower", "apartment residence", "apartment living", "apartment plan"
    ],
    "pool": [
        "pool", "swimming pool", "lap pool", "infinity pool", "plunge pool", "natural pool", "saltwater pool", "chlorine pool", "heated pool", "outdoor pool", "indoor pool", "private pool", "public pool", "community pool", "kids pool", "family pool", "spa pool", "jacuzzi", "hot tub", "wading pool", "splash pool", "pool deck", "poolside", "pool house", "pool area", "pool design", "pool construction", "pool maintenance", "pool cover", "pool fence", "pool safety", "pool lighting", "pool landscaping", "pool tiles", "pool steps", "pool ladder", "pool equipment", "pool filter", "pool pump", "pool heater", "pool cleaner", "pool skimmer", "pool toys", "pool float", "pool party", "pool bar", "pool cabana", "poolside lounge"
    ],
    "spa": [
        "spa", "sauna", "steam room", "hot tub", "jacuzzi", "wellness", "massage room", "relaxation room", "spa bath", "spa pool", "spa center", "spa retreat", "spa suite", "spa area", "spa design", "spa experience", "spa treatment", "spa services", "spa facilities", "spa amenities", "spa therapy", "spa day", "spa package", "spa resort", "spa hotel", "spa villa", "spa garden", "spa lounge", "spa decor", "spa lighting", "spa ambiance", "spa products", "spa oils", "spa towels", "spa robe", "spa slippers", "spa shower", "spa bath salts", "spa candles", "spa music", "spa relaxation", "spa water", "spa poolside", "spa fitness", "spa yoga", "spa meditation", "spa health", "spa luxury", "spa comfort", "spa tranquility"
    ],
    "clubhouse": [
        "clubhouse", "community center", "event hall", "gathering space", "meeting room", "party room", "banquet hall", "recreation center", "social club", "sports club", "youth club", "senior center", "activity room", "function room", "club room", "club lounge", "club bar", "club kitchen", "club dining", "club terrace", "club patio", "club garden", "club pool", "club gym", "club spa", "club office", "club workspace", "club library", "club theater", "club cinema", "club game room", "club billiards", "club ping pong", "club darts", "club music", "club dance", "club fitness", "club yoga", "club meditation", "club art", "club craft", "club workshop", "club seminar", "club training", "club event", "club celebration", "club wedding", "club birthday", "club anniversary", "club meeting"
    ],
    "tiny_house_family_home": [
        "tiny house", "family home", "L-shaped house", "U-shaped house", "compact home", "small house", "micro home", "modular tiny house", "prefab tiny house", "eco tiny house", "mobile tiny house", "portable home", "tiny villa", "tiny cottage", "tiny cabin", "tiny bungalow", "tiny residence", "tiny dwelling", "tiny retreat", "tiny abode", "tiny living", "tiny home design", "tiny home plan", "tiny home layout", "tiny home floorplan", "tiny home blueprint", "tiny home construction", "tiny home build", "tiny home project", "tiny home family", "tiny home kids", "tiny home parents", "tiny home couple", "tiny home pet", "tiny home storage", "tiny home loft", "tiny home stairs", "tiny home kitchen", "tiny home bath", "tiny home bedroom", "tiny home office", "tiny home workspace", "tiny home garden", "tiny home porch", "tiny home deck", "tiny home patio", "tiny home balcony", "tiny home expansion", "tiny home addition"
    ],
    "swimming_pools_natural_ponds": [
        "swimming pool", "natural pond", "eco pool", "bio pool", "pond design", "pond construction", "pond landscaping", "pond maintenance", "pond filter", "pond pump", "pond plants", "pond fish", "pond liner", "pond rocks", "pond waterfall", "pond fountain", "pond lighting", "pond bridge", "pond deck", "pond patio", "pond seating", "pond safety", "pond cover", "pond heater", "pond skimmer", "pond net", "pond cleaning", "pond algae", "pond bacteria", "pond ecosystem", "pond wildlife", "pond habitat", "pond edge", "pond border", "pond wall", "pond basin", "pond depth", "pond shape", "pond size", "pond water", "pond clarity", "pond aeration", "pond oxygen", "pond circulation", "pond overflow", "pond spillway", "pond inlet", "pond outlet", "pond overflow"
    ],
    "outdoor_spas_wellness_areas": [
        "outdoor spa", "wellness area", "outdoor sauna", "outdoor hot tub", "outdoor jacuzzi", "outdoor steam room", "outdoor massage", "outdoor relaxation", "outdoor bath", "outdoor shower", "outdoor pool", "outdoor yoga", "outdoor meditation", "outdoor fitness", "outdoor gym", "outdoor lounge", "outdoor deck", "outdoor patio", "outdoor garden", "outdoor retreat", "outdoor wellness", "outdoor therapy", "outdoor treatment", "outdoor spa design", "outdoor spa plan", "outdoor spa construction", "outdoor spa build", "outdoor spa project", "outdoor spa experience", "outdoor spa package", "outdoor spa services", "outdoor spa amenities", "outdoor spa facilities", "outdoor spa resort", "outdoor spa hotel", "outdoor spa villa", "outdoor spa suite", "outdoor spa garden", "outdoor spa pool", "outdoor spa bath", "outdoor spa shower", "outdoor spa lounge", "outdoor spa relaxation", "outdoor spa tranquility", "outdoor spa comfort", "outdoor spa luxury", "outdoor spa ambiance", "outdoor spa decor"
    ],
    "summer_houses_garden_rooms": [
        "summer house", "garden room", "garden house", "garden studio", "garden office", "garden retreat", "garden shed", "garden cabin", "garden pod", "garden annex", "garden guest house", "garden gym", "garden yoga", "garden meditation", "garden lounge", "garden bar", "garden kitchen", "garden dining", "garden playroom", "garden workshop", "garden craft room", "garden art studio", "garden music room", "garden cinema", "garden theater", "garden library", "garden reading room", "garden games room", "garden billiards", "garden ping pong", "garden darts", "garden fitness", "garden spa", "garden sauna", "garden hot tub", "garden jacuzzi", "garden pool", "garden deck", "garden patio", "garden terrace", "garden balcony", "garden porch", "garden veranda", "garden pergola", "garden gazebo", "garden pavilion", "garden greenhouse", "garden conservatory", "garden sunroom"
    ],
    "commercial_buildings": [
        "commercial building", "coffee shop", "cafe", "restaurant", "bar", "pub", "bakery", "retail store", "shop", "boutique", "salon", "spa", "gym", "fitness center", "office", "workspace", "co-working", "studio", "gallery", "showroom", "clinic", "medical office", "dental office", "pharmacy", "bank", "atm", "supermarket", "grocery store", "market", "mall", "shopping center", "warehouse", "storage", "factory", "workshop", "garage", "car wash", "auto shop", "repair shop", "service center", "laundry", "dry cleaner", "hotel", "motel", "inn", "hostel", "guesthouse", "lodging"
    ],
    "construction_plans": [
        "construction plan", "PDF plan", "DWG plan", "IFC plan", "GLB plan", "blueprint", "floor plan", "site plan", "elevation", "section", "detail drawing", "structural plan", "MEP plan", "HVAC plan", "plumbing plan", "electrical plan", "lighting plan", "fire safety plan", "landscape plan", "roof plan", "foundation plan", "framing plan", "interior plan", "exterior plan", "as-built plan", "shop drawing", "working drawing", "permit drawing", "design drawing", "drafting", "CAD file", "3D model", "BIM file", "rendering", "visualization", "animation", "walkthrough", "cut sheet", "specification", "schedule", "material list", "cost estimate", "quantity takeoff", "project file", "plan set", "drawing set", "plan package"
    ],
    "free_downloads": [
        "free download", "budget plan", "sample unit", "sample plan", "sample drawing", "sample file", "free plan", "free drawing", "free file", "free sample", "free resource", "free pdf", "free dwg", "free ifc", "free glb", "free model", "free 3d", "free bim", "free blueprint", "free floor plan", "free site plan", "free elevation", "free section", "free detail", "free rendering", "free animation", "free walkthrough", "free cut sheet", "free specification", "free schedule", "free material list", "free cost estimate", "free quantity takeoff", "free project file", "free plan set", "free drawing set", "free plan package", "free construction plan", "free design", "free resource pack", "free content", "free asset", "free download link", "free access", "free offer", "freebie"
    ],
    "mep_bim_ready_files": [
        "MEP file", "BIM file", "MEP ready", "BIM ready", "MEP drawing", "BIM drawing", "MEP plan", "BIM plan", "MEP model", "BIM model", "MEP system", "BIM system", "MEP design", "BIM design", "MEP layout", "BIM layout", "MEP coordination", "BIM coordination", "MEP integration", "BIM integration", "MEP documentation", "BIM documentation", "MEP specification", "BIM specification", "MEP schedule", "BIM schedule", "MEP detail", "BIM detail", "MEP section", "BIM section", "MEP elevation", "BIM elevation", "MEP 3D", "BIM 3D", "MEP IFC", "BIM IFC", "MEP dwg", "BIM dwg", "MEP pdf", "BIM pdf", "MEP glb", "BIM glb", "MEP file format", "BIM file format", "MEP export", "BIM export", "MEP import", "BIM import"
    ],
    "ar_previews_cost_estimators": [
        "augmented reality", "AR preview", "AR model", "AR visualization", "AR walkthrough", "AR experience", "AR demo", "AR app", "AR file", "AR plan", "AR design", "AR house", "AR apartment", "AR pool", "AR spa", "AR garden", "AR building", "AR project", "AR construction", "AR architecture", "AR home", "AR preview app", "AR preview file", "AR preview model", "AR preview plan", "AR preview design", "AR preview house", "AR preview apartment", "AR preview pool", "AR preview spa", "AR preview garden", "AR preview building", "AR preview project", "AR preview construction", "AR preview architecture", "cost estimator", "cost estimation", "cost calculator", "price estimator", "price calculator", "budget estimator", "budget calculator", "project estimator", "project calculator", "estimate tool", "estimate app", "estimate file", "estimate model"
    ]
}

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
    Retrieve a product from Firestore by ID, title, name, layout_id, sku, or partial/case-insensitive match. Cleans input and logs all attempts.
    Args:
        product_id (str): The product ID, title, name, or other identifier to retrieve
    Returns:
        Optional[Dict[str, Any]]: Product data if found, None otherwise
    """
    if db is None:
        logger.error("Firestore client not available")
        return None
    try:
        # Clean and normalize input
        import re
        def normalize(s):
            return re.sub(r'\s+', ' ', str(s or '').lower().strip())
        cleaned = product_id
        cleaned = re.sub(r'<.*?>', '', cleaned)  # Remove HTML tags
        cleaned = cleaned.replace('🏡', '').replace('\n', ' ').replace('\r', ' ')
        cleaned = cleaned.split('<br/>')[0]
        cleaned = cleaned.strip()
        cleaned_norm = normalize(cleaned)
        logger.info(f"Looking up product with cleaned input: '{cleaned}' (norm: '{cleaned_norm}')")
        # 1. Try as document ID (normalized string)
        doc = db.collection(PRODUCTS_COLLECTION).document(str(cleaned)).get()
        if doc.exists:
            prod = doc.to_dict()
            if normalize(prod.get("id", "")) == cleaned_norm:
                logger.info(f"Found product by document ID: {cleaned}")
                return prod
        # 2. Try as 'id', 'title', 'name' (normalized)
        docs = db.collection(PRODUCTS_COLLECTION).limit(50).stream()
        for doc in docs:
            prod = doc.to_dict()
            id_str = normalize(prod.get("id", ""))
            title_str = normalize(prod.get("title", ""))
            name_str = normalize(prod.get("name", ""))
            if cleaned_norm == id_str or cleaned_norm == title_str or cleaned_norm == name_str:
                logger.info(f"Found product by normalized id/title/name: {prod.get('title', '')}")
                return prod
        # 3. Try as 'id' field (int)
        try:
            int_id = int(cleaned)
            query = db.collection(PRODUCTS_COLLECTION).where("id", "==", int_id)
            for doc in query.stream():
                logger.info(f"Found product by 'id' (int): {int_id}")
                return doc.to_dict()
        except Exception as e:
            logger.debug(f"Could not convert product_id to int: {e}")

        # 4. Try by 'title' (case-insensitive)
        query = db.collection(PRODUCTS_COLLECTION).where("title", "==", cleaned)
        for doc in query.stream():
            logger.info(f"Found product by 'title': {cleaned}")
            return doc.to_dict()
        query = db.collection(PRODUCTS_COLLECTION).where("title", "==", cleaned_norm) # Use normalized title
        for doc in query.stream():
            logger.info(f"Found product by 'title' (lower): {cleaned_norm}")
            return doc.to_dict()

        # 5. Try by 'name' (case-insensitive)
        query = db.collection(PRODUCTS_COLLECTION).where("name", "==", cleaned)
        for doc in query.stream():
            logger.info(f"Found product by 'name': {cleaned}")
            return doc.to_dict()
        query = db.collection(PRODUCTS_COLLECTION).where("name", "==", cleaned_norm) # Use normalized name
        for doc in query.stream():
            logger.info(f"Found product by 'name' (lower): {cleaned_norm}")
            return doc.to_dict()

        # 6. Try by 'layout_id' (if present)
        query = db.collection(PRODUCTS_COLLECTION).where("layout_id", "==", cleaned)
        for doc in query.stream():
            logger.info(f"Found product by 'layout_id': {cleaned}")
            return doc.to_dict()

        # 7. Try by 'sku' (if present)
        query = db.collection(PRODUCTS_COLLECTION).where("sku", "==", cleaned)
        for doc in query.stream():
            logger.info(f"Found product by 'sku': {cleaned}")
            return doc.to_dict()

        # 8. Partial/case-insensitive match on 'title' and 'name' (range query)
        # Firestore doesn't support case-insensitive search, so fetch a batch and check in Python
        docs = db.collection(PRODUCTS_COLLECTION).where("title", ">=", cleaned).where("title", "<=", cleaned + "\uf8ff").limit(10).stream()
        for doc in docs:
            prod = doc.to_dict()
            title = str(prod.get("title", "") or "")
            name = str(prod.get("name", "") or "")
            if normalize(title) == cleaned_norm or cleaned_norm in normalize(title) or normalize(name) == cleaned_norm or cleaned_norm in normalize(name):
                logger.info(f"Found product by partial/case-insensitive title or name: {title} / {name}")
                return prod
        docs = db.collection(PRODUCTS_COLLECTION).where("name", ">=", cleaned).where("name", "<=", cleaned + "\uf8ff").limit(10).stream()
        for doc in docs:
            prod = doc.to_dict()
            name = str(prod.get("name", "") or "")
            if normalize(name) == cleaned_norm or cleaned_norm in normalize(name):
                logger.info(f"Found product by partial/case-insensitive name: {name}")
                return prod

        # 9. Fallback: scan a batch and fuzzy match on 'title' and 'name'
        docs = db.collection(PRODUCTS_COLLECTION).limit(20).stream()
        from rapidfuzz import process as rapidfuzz_process
        titles = [(str(doc.to_dict().get("title", "") or ""), doc.to_dict()) for doc in docs]
        names = [(str(doc.to_dict().get("name", "") or ""), doc.to_dict()) for doc in docs]
        all_labels = titles + names
        label_texts = [t[0] for t in all_labels]
        if label_texts:
            result = rapidfuzz_process.extractOne(cleaned, label_texts, score_cutoff=80)
            if result:
                idx = label_texts.index(result[0])
                logger.info(f"Found product by fuzzy title/name: {result[0]}")
                return all_labels[idx][1]

        logger.info(f"Product with ID, title, or name '{product_id}' not found after all attempts.")
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve product '{product_id}': {str(e)}")
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

def delete_all_products_from_firestore(batch_size: int = 500) -> None:
    """
    Delete all documents in the Firestore 'products' collection.
    Args:
        batch_size (int): Number of products to process in each batch.
    Returns:
        None
    """
    if db is None:
        logger.error("Firestore client not available. Check GCP credentials and PROJECT_ID.")
        return
    try:
        docs = db.collection(PRODUCTS_COLLECTION).stream()
        docs = list(docs)
        total = len(docs)
        logger.info(f"Found {total} products to delete.")
        for i in range(0, total, batch_size):
            batch = db.batch()
            for doc in docs[i:i+batch_size]:
                batch.delete(doc.reference)
            batch.commit()
            logger.info(f"Deleted batch of {min(batch_size, total-i)} products.")
        logger.info("All products deleted from Firestore.")
    except Exception as e:
        logger.error(f"Failed to delete all products: {str(e)}")

def get_category_from_text(text: str) -> Optional[str]:
    """
    Map user input to a known category using keyword matching, with fuzzy matching fallback.
    """
    text = text.lower()
    # 1. Exact match (any keyword in text)
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(k in text for k in keywords):
            return category
    # 2. Fuzzy match using fuzzywuzzy
    best_score = 0
    best_category = None
    for category, keywords in CATEGORY_KEYWORDS.items():
        for k in keywords:
            score = fuzz.partial_ratio(k, text)
            if score > best_score:
                best_score = score
                best_category = category
    if best_score >= 80:
        return best_category
    # 3. Fuzzy match using rapidfuzz (find best keyword overall)
    all_keywords = [(cat, kw) for cat, kws in CATEGORY_KEYWORDS.items() for kw in kws]
    keyword_list = [kw for _, kw in all_keywords]
    result = rapidfuzz_process.extractOne(text, keyword_list, score_cutoff=80)
    if result:
        matched_keyword = result[0]
        for cat, kw in all_keywords:
            if kw == matched_keyword:
                return cat
    return None

def search_by_category(category: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search Firestore for products by category or product_type.
    """
    if db is None:
        logger.error("Firestore client not available")
        return []
    try:
        # Try category field first
        docs = db.collection(PRODUCTS_COLLECTION).where("category", "==", category).limit(limit).stream()
        results = [doc.to_dict() for doc in docs]
        if results:
            return results
        # Fallback: search by product_type (case-insensitive)
        # Try upper, lower, and title case
        for pt in [category.upper(), category.lower(), category.title()]:
            docs = db.collection(PRODUCTS_COLLECTION).where("product_type", "==", pt).limit(limit).stream()
            results = [doc.to_dict() for doc in docs]
            if results:
                return results
        return []
    except Exception as e:
        logger.error(f"Failed to search by category {category}: {str(e)}")
        return []

def build_product_button_template(product: dict) -> dict:
    """
    Build a Zoko-compatible WhatsApp button template dict for a product.
    """
    logger.info(f"Building button template for product: {json.dumps(product, indent=2, ensure_ascii=False)}")
    image = product.get("image")
    if not image:
        images = product.get("images")
        if images and isinstance(images, list) and len(images) > 0:
            image = images[0].get("src")
        if not image:
            image = "https://via.placeholder.com/300"
    title = str(product.get("title", "Product") or "Product")
    handle = str(product.get("handle", "") or "")
    return {
        "whatsapp_type": "buttonTemplate",
        "template_id": "upsel_01",
        "template_args": [
            image,
            title,
            f"Order {title}",
            f"https://835e8e.myshopify.com/products/{handle}"
        ]
    }

def handle_user_message(text: str) -> dict:
    """
    Handle user message and return products for recognized categories or product button template if matched by ID/title.
    """
    # Sanitize input: remove HTML tags and keep only the first line or before <br/>
    clean_text = re.sub(r'<.*?>', '', text)  # Remove HTML tags
    clean_text = clean_text.split('\n')[0]   # Only first line if multiline
    clean_text = clean_text.split('<br/>')[0]  # Only before <br/> if present
    clean_text = clean_text.strip()

    # Try to match by product ID or title first
    product = get_product_by_id(clean_text)
    if product:
        return build_product_button_template(product)
    # Otherwise, try category search
    category = get_category_from_text(text)
    if category:
        products = search_by_category(category)
        if products:
            message = f"Here are some {category}s:\n\n"
            for p in products:
                message += f"\U0001F3E1 {p.get('title', 'No title')}\n\U0001F4CD Vendor: {p.get('vendor', 'Unknown')}\n\n"
            return {"whatsapp_type": "text", "message": message.strip()}
        else:
            return {"whatsapp_type": "text", "message": f"No {category}s found right now."}
    return {"whatsapp_type": "text", "message": "Please specify what you're looking for (house, apartment, pool, etc.)."}

if __name__ == "__main__":
    export_products_to_json()