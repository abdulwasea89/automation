from src.tools import ProductDatabase
import requests
import re
import json

# Replace with your actual values
ZOKO_API_KEY = "021d048e-5835-4b25-a268-4e3397747220"
ZOKO_ENDPOINT = "https://chat.zoko.io/v2/message"

# Recipient's number (without +)
recipient_number = "923335155379"

# Fetch products from the database
products = ProductDatabase.search_products(query="", limit=10)

def clean_text(text, maxlen):
    text = re.sub(r'<[^>]+>', '', str(text))
    text = re.sub(r'\s+', ' ', text)
    t = text.strip()
    if len(t) > maxlen:
        return t[:maxlen-3] + '...'
    return t

# Format items for interactive list
items = []
for p in products:
    items.append({
        "id": str(p.get("id", "")),
        "payload": str(p.get("id", "")),
        "title": clean_text(p.get("title", ""), 24),
        "description": clean_text(p.get("description", ""), 50)
    })

# Load a real product from exported_products.json
with open("exported_products.json", "r") as f:
    exported_products = json.load(f)
product = exported_products[0]

payload = {
    "channel": "whatsapp",
    "recipient": recipient_number,
    "type": "buttonTemplate",
    "templateId": "zoko_upsell_product_01",
    "templateArgs": [
        product.get("images", [{}])[0].get("src", "https://via.placeholder.com/400x300.jpg"),
        product.get("title", "Product"),
        f"Order {product.get('title', 'Product')}",
        f"https://www.theleva.com/products/{product.get('id', '')}"
    ]
}

# Set headers
headers = {
    "Content-Type": "application/json",
    "apikey": ZOKO_API_KEY
}

# Send request
response = requests.post(ZOKO_ENDPOINT, json=payload, headers=headers, timeout=30)

# Debug output
print("Status Code:", response.status_code)
try:
    print("Response:", response.json())
except Exception as e:
    print("Non-JSON response:", response.text)
    print("Error decoding JSON:", e)
