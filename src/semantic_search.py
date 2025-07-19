from rapidfuzz import fuzz, process
import re
from collections import defaultdict

# Advanced synonym dictionary for expansion (single and multi-word)
SYNONYMS = {
    "home": ["house", "residence", "dwelling", "abode", "domicile", "family home", "tiny house"],
    "apartment": ["flat", "suite", "condo", "unit", "apartment home", "apartment unit"],
    "tiny": ["small", "mini", "compact", "micro", "tiny house", "tiny home"],
    "pool": ["swimming pool", "pond", "lap pool", "infinity pool", "plunge pool"],
    "villa": ["mansion", "estate", "luxury house", "villa home"],
    "family": ["kids", "parents", "children", "family home", "family house"],
    "garden": ["garden room", "garden house", "garden studio", "garden office"],
    "spa": ["wellness", "sauna", "hot tub", "jacuzzi", "relaxation"],
    "clubhouse": ["community center", "event hall", "gathering space"],
    "summer": ["summer house", "garden room"],
    "modular": ["prefab", "modular home", "modular house"],
    "luxury": ["premium", "high-end", "deluxe", "luxury apartment", "luxury house"],
    "studio": ["studio flat", "studio apartment"],
    "cottage": ["cabin", "bungalow", "chalet"],
    "resort": ["hotel", "spa", "retreat"],
    # Add more as needed
}

# For multi-word synonyms, add direct expansion
MULTIWORD_SYNONYMS = {
    "tiny house": ["tiny home", "micro home", "compact house"],
    "family home": ["family house", "home for family"],
    "swimming pool": ["pool", "lap pool", "infinity pool"],
    "garden room": ["garden studio", "garden office"],
    "luxury apartment": ["premium apartment", "deluxe apartment"],
    # Add more as needed
}

def expand_query(query):
    words = re.findall(r"\w+", query.lower())
    expanded = set(words)
    # Expand single-word synonyms
    for word in words:
        expanded.update(SYNONYMS.get(word, []))
    # Expand multi-word synonyms
    for phrase, syns in MULTIWORD_SYNONYMS.items():
        if phrase in query.lower():
            expanded.update(syns)
    return " ".join(expanded)

def hybrid_product_score(query, product):
    title = (product.get('title') or '').lower()
    body = (product.get('body_html') or '').lower()
    query = query.lower()
    # Fuzzy match scores
    title_score = fuzz.token_sort_ratio(query, title)
    body_score = fuzz.token_sort_ratio(query, body)
    # Keyword presence
    keyword_score = sum(1 for word in query.split() if word in title or word in body)
    # Weighted sum: prioritize title, then body, then keyword count
    return 2 * title_score + body_score + 10 * keyword_score

def diversify_results(products, key_fn, max_per_key=2, top_k=5):
    """
    Ensure diversity in results by limiting the number of products with the same key (e.g., title/category).
    """
    buckets = defaultdict(list)
    for p in products:
        buckets[(key_fn(p) or '').lower()].append(p)
    results = []
    for bucket in buckets.values():
        results.extend(bucket[:max_per_key])
        if len(results) >= top_k:
            break
    return results[:top_k]

def search_products_best(query, products, top_k=5):
    expanded_query = expand_query(query)
    scored = [(hybrid_product_score(expanded_query, p), p) for p in products]
    scored.sort(reverse=True, key=lambda x: x[0])
    top_products = [p for _, p in scored]
    # Diversify by title (or use category if available)
    return diversify_results(top_products, key_fn=lambda p: p.get('title', '').lower(), max_per_key=2, top_k=top_k) 