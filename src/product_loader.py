import os
import json
import pandas as pd
from typing import List, Dict, Optional
from deep_translator import GoogleTranslator
from sentence_transformers import SentenceTransformer, util
import numpy as np

# NOTE: Requires 'sentence-transformers' package. Install with: pip install sentence-transformers

class ProductLoader:
    def __init__(self, json_path: str):
        self.json_path = json_path
        self.df = None
        self.avail_col = None
        self.status_col = None
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.product_texts = []
        self.product_embeddings = None
        self.reload_data()

    @staticmethod
    def is_complete_product(product):
        return (
            bool(product.get('image_url') or product.get('Image Src') or product.get('image')) and
            bool(product.get('description') or product.get('Body (HTML)') or product.get('body_html')) and
            bool(product.get('url') or product.get('Handle') or product.get('handle') or product.get('id'))
        )

    def reload_data(self):
        self._load_products(self.json_path)

    def _load_products(self, json_path: str):
        print(f"[DEBUG] Loading products from: {json_path}")
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"JSON file not found: {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.df = pd.DataFrame(data).fillna('')
        # Strengthened filter: remove suspicious/test/empty titles in 'Title', 'title', or 'name' columns (case-insensitive)
        suspicious_titles = {"morgan freeman", "john wood", "pitch deck", "by leva", "", None}
        for col in ['Title', 'title', 'name']:
            if col in self.df.columns:
                self.df = self.df[~self.df[col].str.strip().str.lower().isin(suspicious_titles)]
                self.df = self.df[self.df[col].notnull() & (self.df[col].str.strip() != '')]
        print(f"[DEBUG] Loaded {len(self.df)} products. Titles:")
        print(list(self.df['Title']) if 'Title' in self.df.columns else list(self.df.columns))
        self.df.columns = [col.strip() for col in self.df.columns]
        # Accept 'available' or 'published' as availability column
        self.avail_col = next(
            (col for col in self.df.columns if 'available' in col.lower() or 'published' in col.lower()),
            None
        )
        self.status_col = next((col for col in self.df.columns if 'status' in col.lower()), None)
        if not self.avail_col or not self.status_col:
            raise ValueError("Missing availability or status column in JSON")
        # Handle boolean or string for availability
        avail_values = self.df[self.avail_col]
        if avail_values.dtype == bool:
            avail_mask = avail_values
        else:
            avail_mask = avail_values.astype(str).str.strip().str.lower().isin(['true', 'yes', '1'])
        status_mask = self.df[self.status_col].astype(str).str.strip().str.lower().isin(['active', 'published', 'available', ''])
        df = self.df[avail_mask & status_mask]
        print(f"Loaded {len(df)} available/active products for semantic search")
        self.product_texts = [
            f"{row.get('Title', '')} {row.get('Type', '')} {row.get('Product Category', '')}"
            for _, row in df.iterrows()
        ]
        print("Sample product search texts:", self.product_texts[:5])
        if self.product_texts:
            self.product_embeddings = self.model.encode(self.product_texts, convert_to_tensor=True)
        else:
            self.product_embeddings = None
        self.df = df.reset_index(drop=True)

    def search(self, query: str, lang: str = 'en', max_results: int = 3) -> List[Dict]:
        self.reload_data()  # Ensure data is loaded from JSON before search
        if self.df is None or self.product_embeddings is None or not self.product_texts:
            return []
        q = query.strip()
        query_emb = self.model.encode(q, convert_to_tensor=True)
        cos_scores = util.cos_sim(query_emb, self.product_embeddings)[0].cpu().numpy()
        top_idx = np.argsort(-cos_scores)[:max_results * 2]  # Fetch more to allow filtering
        print("Query:", q)
        print("Top scores:", cos_scores[top_idx])
        results = []
        for idx in top_idx:
            row = self.df.iloc[idx]
            prod = self._localize_product(row.to_dict(), lang)
            if self.is_complete_product(prod):
                results.append(prod)
            if len(results) >= max_results:
                break
        # If all scores are very low, try fuzzy/partial match
        threshold = 0.3
        if not results:
            print(f"[PRODUCT LOADER] Semantic scores low for '{q}', trying partial match.")
            query_words = q.lower().split()
            def match_partial(row):
                name = (row.get('Title', '') or row.get('name', '')).lower()
                return all(word in name for word in query_words)
            fuzzy_matches = [self._localize_product(row.to_dict(), lang) for _, row in self.df.iterrows() if match_partial(row)]
            fuzzy_matches = [p for p in fuzzy_matches if self.is_complete_product(p)]
            print(f"[PRODUCT LOADER] Fuzzy match for query '{q}': {len(fuzzy_matches)} found.")
            return fuzzy_matches[:max_results]
        return results

    def _localize_product(self, product: Dict, lang: str) -> Dict:
        localized = product.copy()
        price = localized.get('Variant Price') or localized.get('price')
        if price:
            try:
                price_val = float(price)
            except Exception:
                price_val = None
            if price_val is not None:
                if lang == 'fr' or lang == 'es':
                    price_val = round(price_val * 0.93, 2)
                    localized['price'] = f"€{price_val}"
                elif lang == 'en':
                    localized['price'] = f"${price_val}"
                else:
                    localized['price'] = f"{price_val} USD"
        desc = localized.get('Body (HTML)', '') or localized.get('description', '')
        if desc and lang != 'en':
            try:
                translated = GoogleTranslator(source='auto', target=lang).translate(desc)
                localized['description'] = translated
            except Exception:
                localized['description'] = desc
        else:
            localized['description'] = desc
        # Always set name, id, image_url, and url with fallback
        localized['name'] = localized.get('Title', localized.get('name', ''))
        localized['id'] = localized.get('Handle', localized.get('id', ''))
        # Image fallback
        localized['image_url'] = (
            localized.get('image_url') or
            localized.get('Image Src') or
            localized.get('image') or
            (localized.get('images', [{}])[0].get('src') if isinstance(localized.get('images'), list) and localized.get('images') else None) or
            "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=400"
        )
        # Description fallback
        if not localized.get('description'):
            localized['description'] = f"Order {localized['name'] or 'Product'}"
        # URL fallback
        localized['url'] = (
            localized.get('url') or
            (f"https://www.theleva.com/products/{localized.get('Handle') or localized.get('handle') or localized.get('id', '')}" if (localized.get('Handle') or localized.get('handle') or localized.get('id')) else "https://www.theleva.com/")
        )
        return localized

    def get_product_with_variants(self, handle: str, lang: str = 'en') -> Optional[Dict]:
        """
        Given a product handle, return the main product info and all its variants.
        """
        if self.df is None:
            return None
        group = self.df[self.df['Handle'] == handle]
        if group.empty:
            return None
        # Main product info (first non-empty Title row)
        main_row = group[group['Title'] != ''].iloc[0] if not group[group['Title'] != ''].empty else group.iloc[0]
        main_info = self._localize_product(main_row.to_dict(), lang)
        # All variants (including main)
        variants = []
        for _, row in group.iterrows():
            variant = self._localize_product(row.to_dict(), lang)
            variants.append(variant)
        main_info['variants'] = variants
        return main_info

    def get_products_paginated(self, handles: List[str], lang: str = 'en', page: int = 1, page_size: int = 3) -> List[Dict]:
        self.reload_data()  # Ensure data is loaded from JSON before paginated fetch
        start = (page - 1) * page_size
        end = start + page_size
        paginated_handles = handles[start:end]
        results = []
        for handle in paginated_handles:
            prod = self.get_product_with_variants(handle, lang=lang)
            if prod and self.is_complete_product(prod):
                results.append(prod)
        return results

import os

# Use the products_export.json from the project root directory
PRODUCTS_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'products_export.json')
if not os.path.isfile(PRODUCTS_JSON_PATH):
    # Fallback: try current working directory
    PRODUCTS_JSON_PATH = os.path.abspath('products_export.json')
product_loader = ProductLoader(PRODUCTS_JSON_PATH)