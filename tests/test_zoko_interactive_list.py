import pytest
from unittest.mock import patch, MagicMock
from src.zoko_client import ZokoClient

@pytest.fixture
def zoko_client():
    return ZokoClient()

def test_format_interactive_list_items(zoko_client):
    items = [
        {"title": "A very long product title that should be truncated", "description": "A very long description that should also be truncated for WhatsApp interactive list.", "payload": "view_1"},
        {"title": "Short title", "description": "Short desc", "payload": "view_2"},
        {"title": "Duplicate payload", "description": "Should be skipped", "payload": "view_1"},
    ]
    formatted = zoko_client.format_interactive_list_items(items)
    assert len(formatted) == 2
    assert formatted[0]["title"] == "A very long product titl"
    assert formatted[0]["description"] == "A very long description that should also be truncated for WhatsApp interactive list."[:72]
    assert formatted[1]["title"] == "Short title"
    assert formatted[1]["payload"] == "view_2"

def test_send_interactive_list_payload_structure(zoko_client):
    items = [
        {"title": "Product 1", "description": "Desc 1", "payload": "view_1"},
        {"title": "Product 2", "description": "Desc 2", "payload": "view_2"},
    ]
    with patch("src.zoko_client.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        result = zoko_client.send_interactive_list("93335155379", "Header", "Body", items)
        assert result is True
        args, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["type"] == "interactive_list"
        assert payload["interactiveList"]["header"]["text"] == "Header"
        assert payload["interactiveList"]["body"]["text"] == "Body"
        assert len(payload["interactiveList"]["list"]["sections"][0]["items"]) == 2
        assert payload["interactiveList"]["list"]["sections"][0]["items"][0]["title"] == "Product 1"
        assert payload["interactiveList"]["list"]["sections"][0]["items"][1]["payload"] == "view_2" 

def test_singular_query_sends_one_product(monkeypatch):
    from src.tools import search_database_func
    # Patch ProductDatabase.search_products to return one product
    monkeypatch.setattr('src.tools.ProductDatabase.search_products', lambda q, limit: [{
        "id": "123",
        "title": "Test Product",
        "description": "A test product.",
        "price": "$10",
        "image_url": "https://example.com/img.png",
        "product_type": "TestType"
    }])
    result = search_database_func("search", query="show me a product")
    data = __import__('json').loads(result)
    assert data["whatsapp_type"] == "buttonTemplate"
    assert data["template"]["template_id"] == "zoko_upsell_product_01"
    assert data["count"] == 1

def test_plural_query_sends_interactive_list(monkeypatch):
    from src.tools import search_database_func
    # Patch ProductDatabase.search_products to return multiple products
    monkeypatch.setattr('src.tools.ProductDatabase.search_products', lambda q, limit: [
        {"id": "1", "title": "Product 1", "description": "Desc 1", "price": "$1", "image_url": "", "product_type": "Type1"},
        {"id": "2", "title": "Product 2", "description": "Desc 2", "price": "$2", "image_url": "", "product_type": "Type2"}
    ])
    result = search_database_func("search", query="show me products")
    data = __import__('json').loads(result)
    assert data["whatsapp_type"] == "interactive_list"
    assert data["template"]["template_id"] == "property_list_interactive"
    assert data["count"] == 2

def test_template_args_are_strings(monkeypatch):
    """Test that template arguments are properly formatted as strings."""
    from src.tools import search_database_func
    # Patch ProductDatabase.search_products to return one product
    monkeypatch.setattr('src.tools.ProductDatabase.search_products', lambda q, limit: [{
        "id": 123,  # Integer ID
        "title": "Test Product",
        "description": "A test product.",
        "price": "$10",
        "image_url": "https://example.com/img.png",
        "product_type": "TestType"
    }])
    result = search_database_func("search", query="show me a product")
    data = __import__('json').loads(result)
    
    # Check template structure
    assert data["whatsapp_type"] == "buttonTemplate"
    assert data["template"]["template_id"] == "zoko_upsell_product_01"
    
    # Check template arguments are strings and match template requirements
    template_args = data["template"]["template_args"]
    assert len(template_args) == 4  # zoko_upsell_product_01 requires 4 args
    
    # Verify all arguments are strings
    assert isinstance(template_args[0], str)  # image_url
    assert isinstance(template_args[1], str)  # title
    assert isinstance(template_args[2], str)  # product_id
    assert isinstance(template_args[3], str)  # button_text
    
    # Verify specific values
    assert template_args[0] == "https://example.com/img.png"  # image_url
    assert template_args[1] == "Test Product"  # title
    assert template_args[2] == "PROD-123"  # product_id
    assert template_args[3] == "Buy Now"  # button_text 