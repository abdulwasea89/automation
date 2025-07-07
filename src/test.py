import sys
import os
import asyncio
import json
from zoko_client import zoko_client
from src.openai_agent import (
    chat_with_agent_enhanced,
    normalize_interactive_list,
    fully_parse_json,
    normalize_button_template
)

# ✅ Format products into valid Zoko interactive_list rows
def format_products_for_zoko(products):
    formatted = []
    for i, p in enumerate(products):
        if p.get("title") and p.get("id"):
            formatted.append({
                "id": p["id"],
                "payload": p["id"],  # Zoko requires this field
                "title": p["title"],
                "description": p.get("description", "")
            })
    return formatted

# ✅ Dummy products for testing
DUMMY_PRODUCTS = [
    {"id": "view_product_001", "title": "Modern Villa", "description": "4 bed, pool, garden"},
    {"id": "view_product_002", "title": "Eco Tiny House", "description": "2 bed, solar, compact"},
    {"id": "view_product_003", "title": "Family Home XL", "description": "5 bed, garage, garden"},
    {"id": "view_product_004", "title": "Urban Loft", "description": "3 bed, city view, smart home"},
    {"id": "view_product_005", "title": "Budget Starter", "description": "2 bed, affordable, cozy"},
]

# ✅ Dummy agent-style interactive list structure
DUMMY_AGENT_INTERACTIVE_LIST = {
    "whatsapp_type": "interactive_list",
    "header": "🏠 LEVA House Projects",
    "body": "Choose a project to view details:",
    "items": format_products_for_zoko(DUMMY_PRODUCTS[:3])
}

def test_send_interactive_list(chat_id):
    print(f"\n🔹 Sending basic interactive list to {chat_id}...")
    header = "🏠 LEVA House Projects"
    body = "Choose a project to view details:"
    items = format_products_for_zoko(DUMMY_PRODUCTS)
    print("Formatted items for Zoko:", json.dumps(items, indent=2))
    if not items:
        print("❌ No valid items to send.")
        return
    success = zoko_client.send_interactive_list(chat_id, header, body, items)
    print("✅ Success!" if success else "❌ Failed!")

def test_send_agent_style_interactive_list(chat_id):
    print(f"\n🔹 Sending agent-style interactive list to {chat_id}...")
    data = DUMMY_AGENT_INTERACTIVE_LIST
    print("Formatted agent-style items:", json.dumps(data["items"], indent=2))
    if not data["items"]:
        print("❌ No valid items to send.")
        return
    success = zoko_client.send_interactive_list(chat_id, data["header"], data["body"], data["items"])
    print("✅ Success!" if success else "❌ Failed!")

def test_product_template(chat_id):
    print("\n🔹 Testing agent-generated buttonTemplate...")
    response = asyncio.run(chat_with_agent_enhanced("I need one bedroom house", chat_id=chat_id))
    if isinstance(response, dict) and "search_one_product_with_handoff_response" in response:
        results = response["search_one_product_with_handoff_response"].get("results", [])
        if results and isinstance(results[0], dict):
            response = results[0]
    print("Single product response:", response)

    print("\n🔹 Testing agent-generated interactive_list...")
    response = asyncio.run(chat_with_agent_enhanced("I need all two bedroom houses", chat_id=chat_id))
    if isinstance(response, dict) and "search_products_with_handoff_response" in response:
        results = response["search_products_with_handoff_response"].get("results", [])
        if results and isinstance(results[0], dict):
            response = normalize_interactive_list(results[0])
        elif results and isinstance(results[0], str):
            try:
                import orjson
                parsed = orjson.loads(results[0])
                response = normalize_interactive_list(parsed)
            except Exception:
                pass
    print("Multiple product response:", response)

def test_edge_cases(chat_id):
    print("\n🔹 Testing edge cases and parsing...")

    malformed = '{"whatsapp_type": "buttonTemplate", "template_id": "zoko_upsell_product_01", "template_args": ["img", "title"]'
    try:
        parsed = fully_parse_json(malformed)
        print("✅ Malformed JSON parsed:", parsed)
    except Exception as e:
        print("❌ Malformed JSON error:", e)

    codeblock = '```json\n{"whatsapp_type": "interactive_list", "header": "H", "body": "B", "items": []}\n```'
    try:
        parsed = fully_parse_json(codeblock)
        print("✅ Code block JSON parsed:", parsed)
    except Exception as e:
        print("❌ Code block JSON error:", e)

    tool_plan = '{"tool_code": "search_products_with_handoff", "tool_args": {"query": "villa"}}'
    try:
        parsed = fully_parse_json(tool_plan)
        print("✅ Tool call plan parsed:", parsed)
    except Exception as e:
        print("❌ Tool call parse error:", e)

    agent_output = '{"whatsapp_type": "interactive_list", "header": "H", "body": "B", "items": [{"title": "T", "description": "D", "payload": "P"}]}'
    parsed = fully_parse_json(agent_output)
    normalized = normalize_interactive_list(parsed)
    print("✅ Normalized output:", normalized)
    assert all(k in normalized for k in ("header", "body", "items")), "❌ Interactive list missing keys"
    print("✅ All edge case tests passed!")

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_zoko.py <whatsapp_chat_id>")
        sys.exit(1)

    chat_id = sys.argv[1]
    test_send_interactive_list(chat_id)
    test_send_agent_style_interactive_list(chat_id)
    test_product_template(chat_id)
    test_edge_cases(chat_id)

if __name__ == "__main__":
    main()
