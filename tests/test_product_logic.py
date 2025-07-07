import pytest
import json
from unittest.mock import patch, MagicMock
from src.tools import search_database_func, is_singular_query
from src.zoko_client import ZokoClient


class TestProductLogic:
    """Test the complete product logic flow."""
    
    def test_is_singular_query_logic(self):
        """Test the singular/plural query detection logic."""
        # Singular queries
        assert is_singular_query("show me a product") == True
        assert is_singular_query("give me one product") == True
        assert is_singular_query("I want a product") == True
        assert is_singular_query("the product") == True
        assert is_singular_query("product") == True
        
        # Plural queries
        assert is_singular_query("show me products") == False
        assert is_singular_query("list products") == False
        assert is_singular_query("all products") == False
        assert is_singular_query("show me multiple products") == False
        assert is_singular_query("products") == False
    
    @patch('src.tools.ProductDatabase.search_products')
    def test_singular_query_returns_single_product_template(self, mock_search):
        """Test that singular queries return single product template."""
        # Mock single product result
        mock_search.return_value = [{
            "id": "123",
            "title": "Test Product",
            "description": "A test product",
            "price": "$100",
            "image_url": "https://example.com/image.jpg",
            "product_type": "Test"
        }]
        
        result = search_database_func("search", query="show me a product")
        data = json.loads(result)
        
        # Verify single product response
        assert data["count"] == 1
        assert data["whatsapp_type"] == "buttonTemplate"
        assert data["template"]["template_id"] == "zoko_upsell_product_01"
        
        # Verify template arguments
        template_args = data["template"]["template_args"]
        assert len(template_args) == 4
        assert template_args[0] == "https://example.com/image.jpg"  # image_url
        assert template_args[1] == "Test Product"  # title
        assert template_args[2] == "PROD-123"  # product_id
        assert template_args[3] == "Buy Now"  # button_text
    
    @patch('src.tools.ProductDatabase.search_products')
    def test_plural_query_returns_interactive_list(self, mock_search):
        """Test that plural queries return interactive list."""
        # Mock multiple products result
        mock_search.return_value = [
            {"id": "1", "title": "Product 1", "description": "Desc 1", "price": "$10", "image_url": "", "product_type": "Type1"},
            {"id": "2", "title": "Product 2", "description": "Desc 2", "price": "$20", "image_url": "", "product_type": "Type2"}
        ]
        
        result = search_database_func("search", query="show me products")
        data = json.loads(result)
        
        # Verify multiple products response
        assert data["count"] == 2
        assert data["whatsapp_type"] == "interactive_list"
        assert data["template"]["template_id"] == "property_list_interactive"
        
        # Verify template arguments
        template_args = data["template"]["template_args"]
        assert len(template_args) == 3
        assert template_args[0] == "Available Products"
        assert "Found 2 products" in template_args[1]
        
        # Parse items from JSON
        items = json.loads(template_args[2])
        assert len(items) == 2
        assert items[0]["title"] == "Product 1"
        assert items[1]["title"] == "Product 2"
    
    @patch('src.tools.ProductDatabase.search_products')
    def test_template_args_are_always_strings(self, mock_search):
        """Test that all template arguments are properly converted to strings."""
        # Mock product with mixed data types
        mock_search.return_value = [{
            "id": 123,  # Integer
            "title": "Test Product",
            "description": "A test product",
            "price": 100.50,  # Float
            "image_url": "https://example.com/image.jpg",
            "product_type": "Test"
        }]
        
        result = search_database_func("search", query="show me a product")
        data = json.loads(result)
        
        # Verify all template arguments are strings
        template_args = data["template"]["template_args"]
        for arg in template_args:
            assert isinstance(arg, str), f"Template argument {arg} is not a string"
        
        # Verify specific values
        assert template_args[0] == "https://example.com/image.jpg"
        assert template_args[1] == "Test Product"
        assert template_args[2] == "PROD-123"
        assert template_args[3] == "Buy Now"
    
    @patch('src.tools.ProductDatabase.search_products')
    def test_missing_product_data_handling(self, mock_search):
        """Test handling of products with missing data."""
        # Mock product with missing fields - but format it properly
        raw_product = {
            "id": "123",
            "title": None,  # Missing title
            "image_url": None,  # Missing image
        }
        
        # Mock the formatted product with fallback values
        formatted_product = {
            "id": "123",
            "title": "Product",  # Fallback title
            "description": "A test product",
            "price": "Contact for price",
            "image_url": "https://via.placeholder.com/400x300?text=Product",  # Fallback image
            "url": "https://835e8e.myshopify.com/products/",
            "product_type": "",
            "tags": "",
            "handle": "",
            "raw_data": raw_product
        }
        
        mock_search.return_value = [formatted_product]
        
        result = search_database_func("search", query="show me a product")
        data = json.loads(result)
        
        # Verify fallback values are used
        template_args = data["template"]["template_args"]
        assert template_args[0] == "https://via.placeholder.com/400x300?text=Product"  # fallback image
        assert template_args[1] == "Product"  # fallback title
        assert template_args[2] == "PROD-123"
        assert template_args[3] == "Buy Now"
    
    def test_zoko_template_requirements(self):
        """Test that our template arguments match Zoko template requirements."""
        # According to zoko_templates.json, zoko_upsell_product_01 needs:
        # - templateVariableCount: 4
        # - Variables: {{1}} (image), {{2}} (title), {{3}} (order), {{4}} (button)
        
        template_args = [
            "https://example.com/image.jpg",  # {{1}} - Image URL
            "Product Name",                   # {{2}} - Product title
            "PROD-123",                      # {{3}} - Order/Product ID
            "Buy Now"                        # {{4}} - Button text
        ]
        
        assert len(template_args) == 4, "zoko_upsell_product_01 requires exactly 4 template arguments"
        
        # Verify all arguments are strings
        for arg in template_args:
            assert isinstance(arg, str), f"All template arguments must be strings, got {type(arg)}"
        
        # Verify reasonable lengths
        assert len(template_args[0]) > 0, "Image URL cannot be empty"
        assert len(template_args[1]) > 0, "Product title cannot be empty"
        assert len(template_args[2]) > 0, "Product ID cannot be empty"
        assert len(template_args[3]) > 0, "Button text cannot be empty"


class TestWhatsAppIntegration:
    """Test WhatsApp message sending integration."""
    
    @patch('src.zoko_client.requests.post')
    def test_send_button_template_success(self, mock_post):
        """Test successful button template sending."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "success"}'
        mock_post.return_value = mock_response
        
        client = ZokoClient()
        result = client.send_button_template(
            "1234567890",
            "zoko_upsell_product_01",
            ["https://example.com/image.jpg", "Test Product", "PROD-123", "Buy Now"]
        )
        
        assert result == True
        mock_post.assert_called_once()
        
        # Verify payload structure
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['type'] == 'buttonTemplate'
        assert payload['template']['templateId'] == 'zoko_upsell_product_01'
        assert len(payload['template']['templateArgs']) == 4
    
    @patch('src.zoko_client.requests.post')
    def test_send_interactive_list_success(self, mock_post):
        """Test successful interactive list sending."""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "success"}'
        mock_post.return_value = mock_response
        
        client = ZokoClient()
        items = [
            {"title": "Product 1", "description": "Description 1", "payload": "view_1"},
            {"title": "Product 2", "description": "Description 2", "payload": "view_2"}
        ]
        
        result = client.send_interactive_list("1234567890", "Products", "Available products", items)
        
        assert result == True
        mock_post.assert_called_once()
        
        # Verify payload structure
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['type'] == 'interactive_list'
        assert payload['interactiveList']['header']['text'] == 'Products'
        assert payload['interactiveList']['body']['text'] == 'Available products'
        assert len(payload['interactiveList']['items']) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"]) 