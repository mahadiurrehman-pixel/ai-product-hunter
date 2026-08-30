"""
Tests for eBay response parser.
"""
import json
from decimal import Decimal

import pytest

from services.ebay.parser import EbayParser
from services.ebay.exceptions import EbayInvalidResponseError


class TestEbayParser:
    """Test eBay response parser."""

    @pytest.fixture
    def mock_search_response(self):
        """Load mock search response."""
        with open("tests/mocks/ebay_search_response.json") as f:
            return json.load(f)

    @pytest.fixture
    def parser(self):
        """Create parser instance."""
        return EbayParser()

    def test_parse_search_response_success(self, parser, mock_search_response):
        """Test parsing successful search response."""
        result = parser.parse_search_response(mock_search_response)

        assert result["total"] == 1523
        assert result["limit"] == 5
        assert result["offset"] == 0
        assert result["items_count"] == 5
        assert len(result["items"]) == 5

    def test_parse_search_response_invalid_type(self, parser):
        """Test parsing with invalid response type."""
        with pytest.raises(EbayInvalidResponseError):
            parser.parse_search_response("not a dict")

    def test_parse_search_response_invalid_items(self, parser):
        """Test parsing with invalid itemSummaries."""
        with pytest.raises(EbayInvalidResponseError):
            parser.parse_search_response({"itemSummaries": "not a list"})

    def test_parse_item_summary_complete(self, parser, mock_search_response):
        """Test parsing complete item summary."""
        item_data = mock_search_response["itemSummaries"][0]

        result = parser.parse_item_summary(item_data)

        assert result["item_id"] == "v1|334567891234|0"
        assert (
            result["title"]
            == "Wireless Bluetooth Earbuds with Charging Case - Noise Cancelling"
        )
        assert result["price_value"] == Decimal("29.99")
        assert result["price_currency"] == "USD"
        assert result["image_url"] is not None
        assert result["condition"] == "New"
        assert result["seller_username"] == "tech_deals_usa"
        assert result["seller_feedback_percentage"] == 98.5
        assert result["estimated_sold_quantity"] == 143

    def test_parse_item_summary_minimal(self, parser):
        """Test parsing item with minimal fields."""
        item_data = {
            "itemId": "v1|999999999|0",
            "title": "Minimal Product",
            "price": {"value": "10.00", "currency": "USD"},
            "itemWebUrl": "https://ebay.com/itm/999999999",
        }

        result = parser.parse_item_summary(item_data)

        assert result["item_id"] == "v1|999999999|0"
        assert result["title"] == "Minimal Product"
        assert result["price_value"] == Decimal("10.00")
        assert result["seller_username"] is None
        assert result["estimated_sold_quantity"] is None

    def test_parse_item_summary_missing_item_id(self, parser):
        """Test parsing item without itemId."""
        item_data = {"title": "Product", "price": {"value": "10.00"}}

        with pytest.raises(EbayInvalidResponseError):
            parser.parse_item_summary(item_data)

    def test_parse_item_summary_missing_price(self, parser):
        """Test parsing item without price."""
        item_data = {
            "itemId": "v1|123|0",
            "title": "Product",
            "itemWebUrl": "https://ebay.com/itm/123",
        }

        result = parser.parse_item_summary(item_data)

        # Should default to 0.0
        assert result["price_value"] == Decimal("0.0")

    def test_parse_item_summary_calculated_shipping(self, parser, mock_search_response):
        """Test parsing item with calculated shipping."""
        item_data = mock_search_response["itemSummaries"][4]  # Last item

        result = parser.parse_item_summary(item_data)

        # Should handle calculated shipping
        assert result["shipping_options"] is not None

    def test_parse_item_summary_preserves_raw_data(self, parser, mock_search_response):
        """Test that raw data is preserved."""
        item_data = mock_search_response["itemSummaries"][0]

        result = parser.parse_item_summary(item_data)

        assert result["raw_data"] == item_data

    def test_parse_item_summary_currency_handling(self, parser):
        """Test handling of different currencies."""
        item_data = {
            "itemId": "v1|123|0",
            "title": "Product",
            "price": {"value": "25.50", "currency": "GBP"},
            "itemWebUrl": "https://ebay.co.uk/itm/123",
        }

        result = parser.parse_item_summary(item_data)

        assert result["price_currency"] == "GBP"

    def test_parse_item_summary_categories(self, parser, mock_search_response):
        """Test category parsing."""
        item_data = mock_search_response["itemSummaries"][0]

        result = parser.parse_item_summary(item_data)

        assert result["category_id"] == "15032"
        assert result["category_name"] == "Portable Audio & Headphones"

    def test_parse_item_summary_product_aspects(self, parser, mock_search_response):
        """Test product aspects parsing."""
        item_data = mock_search_response["itemSummaries"][2]  # Has product aspects

        result = parser.parse_item_summary(item_data)

        assert result["product_brand"] == "TechPro"
        assert result["product_aspects"] is not None
        assert "Brand" in result["product_aspects"]
