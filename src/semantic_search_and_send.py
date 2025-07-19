import asyncio
import json
import re
from src.product_loader import product_loader
from src.translation_utils import get_translation
from src.zoko_client import zoko_client
from src.openai_agent import chat_with_agent_enhanced

async def main():
    query = "Hi"  # AI-driven query
    phone_number = "923335155379"
    lang = "en"

    # Use the AI agent to process the query
    agent_response = await chat_with_agent_enhanced(query, chat_id=phone_number, lang=lang)
    print(f"Agent response: {agent_response}")

    # Robustly parse the message for interactive list
    parsed_message = None
    msg = agent_response.get("message")
    if isinstance(msg, str):
        try:
            parsed_message = json.loads(msg)
            print("Parsed message:", parsed_message)
        except Exception as e:
            print("Standard JSON parse failed:", e)
            # Try to extract JSON substring
            try:
                json_str = msg[msg.find("{"):msg.rfind("}")+1]
                parsed_message = json.loads(json_str)
                print("Extracted JSON substring parsed:", parsed_message)
            except Exception as e2:
                print("Substring JSON parse failed:", e2)
                # As a last resort, try to extract items by regex (very basic)
                titles = re.findall(r'"title"\s*:\s*"([^"]+)"', msg)
                descriptions = re.findall(r'"description"\s*:\s*"([^"]+)"', msg)
                payloads = re.findall(r'"payload"\s*:\s*"([^"]+)"', msg)
                if titles and descriptions and payloads:
                    items = []
                    for t, d, p in zip(titles, descriptions, payloads):
                        items.append({
                            "title": t[:24],
                            "description": d[:72],
                            "payload": p[:200]
                        })
                    print("Extracted items by regex:", items)
                    # You can now send this as an interactive list if you have header/body
                    header = "LEVA Houses"
                    body = "Choose an option:"
                    result = await zoko_client.send_interactive_list(
                        phone_number,
                        header,
                        body,
                        items
                    )
                    print(f"Interactive list sent (regex fallback): {result}")
                    return
                else:
                    print("Could not extract items by regex. Message was:", msg[:200])
                    parsed_message = None

    # If the agent returns an interactive list, send it and return
    if parsed_message and isinstance(parsed_message, dict) and parsed_message.get("whatsapp_type") == "interactive_list":
        # Support both normalized and nested formats
        if "items" in parsed_message and "header" in parsed_message and "body" in parsed_message:
            # Normalized format
            header = parsed_message.get("header", "LEVA Houses")
            body = parsed_message.get("body", "Choose an option:")
            items = parsed_message.get("items", [])
        elif "interactiveList" in parsed_message:
            # Nested format
            interactive = parsed_message["interactiveList"]
            list_obj = interactive["list"]
            body = interactive.get("body", {}).get("text", "Choose an option:")
            sections = list_obj.get("sections", [])
            items = []
            for section in sections:
                for item in section.get("items", []):
                    items.append({
                        "title": item.get("title", "")[:24],
                        "description": item.get("description", "")[:72],
                        "payload": str(item.get("payload", ""))[:200]
                    })
            header = list_obj.get("title", "LEVA Houses")
        else:
            print("Unrecognized interactive list format:", parsed_message)
            return

        print("Sending interactive list with items:", items)
        result = await zoko_client.send_interactive_list(
            phone_number,
            header,
            body,
            items
        )
        print(f"Interactive list sent: {result}")
        return

    # If the agent returns a buttonTemplate, send it
    if agent_response.get("whatsapp_type") == "buttonTemplate":
        template_id = agent_response.get("template_id", "zoko_upsell_product_01")
        template_args = agent_response.get("template_args")
        if not template_args:
            # Fallback: build template_args from product info if possible
            product_name = agent_response.get("header") or agent_response.get("name") or "Product"
            template_args = [
                agent_response.get("image_url", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=400"),
                product_name,
                get_translation("order_product", lang, product=product_name),
                agent_response.get("url", "https://www.theleva.com/")
            ]
        result = await zoko_client.send_button_template(
            phone_number,
            template_id,
            template_args
        )
        print(f"Button template sent: {result}")
        return

    # Fallback: semantic search and manual send
    print("Agent did not return a buttonTemplate or interactive list, falling back to semantic search.")
    products = product_loader.search("PAVO 90", lang=lang, max_results=1)
    if not products:
        print(f"No products found for query: PAVO 90")
        return
    product = products[0]
    template_args = [
        product.get("image_url", "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=400"),
        product.get("name", product.get("Title", "Product")),
        get_translation("order_product", lang, product=product.get("name", product.get("Title", "Product"))),
        product.get("url", "https://www.theleva.com/")
    ]
    result = await zoko_client.send_button_template(
        phone_number,
        "zoko_upsell_product_01",
        template_args
    )
    print(f"Button template sent (fallback): {result}")

if __name__ == "__main__":
    asyncio.run(main()) 