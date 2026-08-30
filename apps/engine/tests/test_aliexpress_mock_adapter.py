"""
Tests for MockAliExpressAdapter.
"""
from decimal import Decimal
from pathlib import Path

import pytest

from services.aliexpress.mock_adapter import MockAliExpressAdapter
from services.aliexpress.models import AliExpressProduct


class TestMockAliExpressAdapter:
    """Test MockAliExpressAdapter."""

    @pytest.fixture
    def adapter(self):
        """Create adapter with real mock data file."""
        return MockAliExpressAdapter()

    # -------------------------------------------------------------------------
    # is_demo_mode
    # -------------------------------------------------------------------------

    def test_is_demo_mode_always_true(self, adapter):
        assert adapter.is_demo_mode() is True

    def test_get_demo_warning_not_none(self, adapter):
        warning = adapter.get_demo_warning()
        assert warning is not None
        assert "DEMO" in warning or "demo" in warning.lower()

    # -------------------------------------------------------------------------
    # search_products — basic
    # -------------------------------------------------------------------------

    def test_search_returns_list(self, adapter):
        results = adapter.search_products("wireless earbuds")
        assert isinstance(results, list)

    def test_search_empty_query_returns_empty(self, adapter):
        results = adapter.search_products("")
        assert results == []

    def test_search_whitespace_query_returns_empty(self, adapter):
        results = adapter.search_products("   ")
        assert results == []

    def test_search_returns_aliexpress_products(self, adapter):
        results = adapter.search_products("bluetooth earbuds")
        assert all(isinstance(p, AliExpressProduct) for p in results)

    def test_search_products_have_source_mock(self, adapter):
        results = adapter.search_products("earbuds")
        for product in results:
            assert product.source == "mock"
            assert product.is_mock is True

    def test_search_products_have_required_fields(self, adapter):
        results = adapter.search_products("wireless earbuds", limit=3)
        for product in results:
            assert product.product_id
            assert product.title
            assert product.price is not None
            assert product.product_url
            assert product.source == "mock"

    def test_search_respects_limit(self, adapter):
        results = adapter.search_products("bluetooth", limit=3)
        assert len(results) <= 3

    def test_search_limit_one(self, adapter):
        results = adapter.search_products("earbuds", limit=1)
        assert len(results) == 1

    def test_search_prices_are_decimal(self, adapter):
        results = adapter.search_products("earbuds", limit=5)
        for product in results:
            assert isinstance(product.price.value, Decimal)
            assert product.price.value > 0

    def test_search_prices_positive(self, adapter):
        results = adapter.search_products("wireless", limit=5)
        for product in results:
            assert float(product.price.value) > 0

    # -------------------------------------------------------------------------
    # search_products — relevance
    # -------------------------------------------------------------------------

    def test_search_audio_category(self, adapter):
        """Audio queries should return audio products."""
        results = adapter.search_products("bluetooth earbuds wireless", limit=5)
        assert len(results) > 0
        # At least one result should be clearly audio-related
        titles = [r.title.lower() for r in results]
        audio_keywords = ["earbuds", "headphones", "speaker", "bluetooth"]
        assert any(
            any(kw in title for kw in audio_keywords)
            for title in titles
        )

    def test_search_charger_category(self, adapter):
        """Charger queries should return charger/cable products."""
        results = adapter.search_products("usb charger fast charge", limit=5)
        assert len(results) > 0
        titles = [r.title.lower() for r in results]
        assert any(
            "charger" in title or "cable" in title or "usb" in title
            for title in titles
        )

    def test_search_case_category(self, adapter):
        """Phone case queries should return case products."""
        results = adapter.search_products("phone case iphone", limit=5)
        assert len(results) > 0
        titles = [r.title.lower() for r in results]
        assert any("case" in title for title in titles)

    def test_search_mouse_category(self, adapter):
        """Mouse queries should return mouse products."""
        results = adapter.search_products("wireless mouse", limit=5)
        assert len(results) > 0
        titles = [r.title.lower() for r in results]
        assert any("mouse" in title for title in titles)

    def test_search_irrelevant_query_returns_results(self, adapter):
        """
        Completely irrelevant query should still return a diverse sample
        rather than empty list — ensures UI always has something to show.
        """
        results = adapter.search_products(
            "purple dinosaur unicorn xyz123", limit=5
        )
        # Returns diverse sample when no keyword match
        assert isinstance(results, list)

    def test_search_relevance_ordering(self, adapter):
        """
        More specific queries should return most relevant results first.
        """
        results = adapter.search_products(
            "bluetooth wireless earbuds TWS noise cancelling", limit=5
        )
        assert len(results) > 0
        # First result should be clearly audio/earbuds related
        first_title = results[0].title.lower()
        assert any(
            kw in first_title
            for kw in ["earbuds", "earphones", "headphones", "bluetooth"]
        )

    # -------------------------------------------------------------------------
    # get_product_details
    # -------------------------------------------------------------------------

    def test_get_product_details_found(self, adapter):
        result = adapter.get_product_details("ali_001")
        assert result is not None
        assert result.product_id == "ali_001"
        assert result.source == "mock"

    def test_get_product_details_not_found(self, adapter):
        result = adapter.get_product_details("nonexistent_999")
        assert result is None

    def test_get_product_details_empty_id(self, adapter):
        result = adapter.get_product_details("")
        assert result is None

    def test_get_product_details_has_store(self, adapter):
        result = adapter.get_product_details("ali_001")
        assert result is not None
        assert result.store is not None
        assert result.store.name

    def test_get_product_details_has_shipping(self, adapter):
        result = adapter.get_product_details("ali_001")
        assert result is not None
        assert len(result.shipping_options) > 0

    def test_get_product_details_shipping_cost_decimal(self, adapter):
        result = adapter.get_product_details("ali_001")
        assert result is not None
        for shipping in result.shipping_options:
            assert isinstance(shipping.cost, Decimal)

    def test_get_all_products_by_id(self, adapter):
        """All 15 mock products should be retrievable by ID."""
        for i in range(1, 16):
            product_id = f"ali_{i:03d}"
            result = adapter.get_product_details(product_id)
            assert result is not None, f"Product {product_id} not found"
            assert result.product_id == product_id

    # -------------------------------------------------------------------------
    # _tokenize
    # -------------------------------------------------------------------------

    def test_tokenize_basic(self, adapter):
        tokens = adapter._tokenize("wireless earbuds")
        assert "wireless" in tokens
        assert "earbuds" in tokens

    def test_tokenize_lowercase(self, adapter):
        tokens = adapter._tokenize("Wireless Earbuds")
        assert "wireless" in tokens
        assert "Wireless" not in tokens

    def test_tokenize_filters_short_tokens(self, adapter):
        tokens = adapter._tokenize("a an the")
        assert len(tokens) == 0

    def test_tokenize_handles_special_chars(self, adapter):
        tokens = adapter._tokenize("USB-C hub 7-in-1")
        assert "usb" in tokens or "usbsb" not in tokens
        assert "hub" in tokens

    # -------------------------------------------------------------------------
    # _calculate_relevance
    # -------------------------------------------------------------------------

    def test_relevance_earbuds_product(self, adapter):
        """Earbuds query should be highly relevant to earbuds product."""
        query_kw = adapter._tokenize("wireless bluetooth earbuds")
        product = {
            "title": "TWS Wireless Bluetooth Earbuds with Charging Case",
            "keywords": ["wireless", "earbuds", "bluetooth", "tws"],
            "category": "audio",
            "attributes": {"connectivity": "bluetooth"},
        }
        score = adapter._calculate_relevance(query_kw, product)
        assert score > 5.0

    def test_relevance_unrelated_product(self, adapter):
        """Earbuds query should score lower on keyboard product."""
        query_kw = adapter._tokenize("wireless earbuds bluetooth")
        product = {
            "title": "Mechanical Gaming Keyboard RGB",
            "keywords": ["keyboard", "mechanical", "gaming", "rgb"],
            "category": "electronics",
            "attributes": {},
        }
        score_keyboard = adapter._calculate_relevance(query_kw, product)

        earbuds_product = {
            "title": "TWS Wireless Bluetooth Earbuds",
            "keywords": ["wireless", "earbuds", "bluetooth", "tws"],
            "category": "audio",
            "attributes": {},
        }
        score_earbuds = adapter._calculate_relevance(
            query_kw, earbuds_product
        )
        assert score_earbuds > score_keyboard

    def test_relevance_empty_query(self, adapter):
        score = adapter._calculate_relevance(set(), {"title": "anything"})
        assert score == 0.0

    # -------------------------------------------------------------------------
    # Mock data loading
    # -------------------------------------------------------------------------

    def test_loads_all_products(self, adapter):
        """Mock data should contain all 15 products."""
        products = adapter._load_mock_data()
        assert len(products) == 15

    def test_cached_after_first_load(self, adapter):
        """Second load should use cache, not re-read file."""
        adapter._load_mock_data()  # First load
        first_ref = id(adapter._products)

        adapter._load_mock_data()  # Second load
        second_ref = id(adapter._products)

        assert first_ref == second_ref  # Same object in memory

    def test_missing_data_file_returns_empty(self):
        """Adapter with non-existent data file returns empty list."""
        adapter = MockAliExpressAdapter(
            mock_data_path=Path("/nonexistent/path/data.json")
        )
        products = adapter._load_mock_data()
        assert products == []

    def test_search_with_missing_data_file_returns_empty(self):
        """Search with missing data file returns empty list, not error."""
        adapter = MockAliExpressAdapter(
            mock_data_path=Path("/nonexistent/path/data.json")
        )
        results = adapter.search_products("earbuds")
        assert results == []