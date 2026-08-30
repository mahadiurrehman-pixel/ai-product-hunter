"""
Tests for AliExpress data models.
"""
from decimal import Decimal
from datetime import datetime

import pytest

from services.aliexpress.models import (
    AliExpressPrice,
    AliExpressProduct,
    AliExpressShipping,
    AliExpressStore,
)


class TestAliExpressPrice:
    """Test AliExpressPrice model."""

    def test_basic_price(self):
        price = AliExpressPrice(value=Decimal("8.99"), currency="USD")
        assert price.value == Decimal("8.99")
        assert price.currency == "USD"
        assert price.original_value is None

    def test_price_with_original(self):
        price = AliExpressPrice(
            value=Decimal("8.99"),
            currency="USD",
            original_value=Decimal("12.99"),
        )
        assert price.original_value == Decimal("12.99")

    def test_price_to_dict(self):
        price = AliExpressPrice(
            value=Decimal("8.99"),
            currency="USD",
            original_value=Decimal("12.99"),
        )
        d = price.to_dict()
        assert d["value"] == 8.99
        assert d["currency"] == "USD"
        assert d["original_value"] == 12.99

    def test_price_to_dict_no_original(self):
        price = AliExpressPrice(value=Decimal("5.00"), currency="USD")
        d = price.to_dict()
        assert d["original_value"] is None


class TestAliExpressStore:
    """Test AliExpressStore model."""

    def test_basic_store(self):
        store = AliExpressStore(name="TechPro Store")
        assert store.name == "TechPro Store"
        assert store.store_id is None
        assert store.url is None

    def test_full_store(self):
        store = AliExpressStore(
            name="TechPro Store",
            store_id="store_001",
            url="https://www.aliexpress.com/store/store_001",
            positive_feedback_rate=98.5,
        )
        d = store.to_dict()
        assert d["name"] == "TechPro Store"
        assert d["store_id"] == "store_001"
        assert d["positive_feedback_rate"] == 98.5


class TestAliExpressShipping:
    """Test AliExpressShipping model."""

    def test_free_shipping(self):
        shipping = AliExpressShipping(
            method="AliExpress Standard Shipping",
            cost=Decimal("0.00"),
        )
        assert shipping.cost == Decimal("0.00")
        assert shipping.currency == "USD"

    def test_paid_shipping(self):
        shipping = AliExpressShipping(
            method="AliExpress Standard Shipping",
            cost=Decimal("2.99"),
            estimated_days_min=15,
            estimated_days_max=30,
        )
        d = shipping.to_dict()
        assert d["cost"] == 2.99
        assert d["estimated_days_min"] == 15
        assert d["estimated_days_max"] == 30


class TestAliExpressProduct:
    """Test AliExpressProduct model."""

    @pytest.fixture
    def sample_product(self):
        return AliExpressProduct(
            product_id="ali_001",
            title="TWS Wireless Bluetooth Earbuds",
            price=AliExpressPrice(
                value=Decimal("8.99"),
                currency="USD",
            ),
            product_url="https://www.aliexpress.com/item/ali_001.html",
            source="mock",
            store=AliExpressStore(
                name="TechPro Store",
                store_id="store_001",
            ),
            rating_score=4.8,
            review_count=2341,
            orders_count=8523,
        )

    def test_is_mock_true(self, sample_product):
        assert sample_product.is_mock is True

    def test_is_mock_false(self):
        product = AliExpressProduct(
            product_id="real_001",
            title="Real Product",
            price=AliExpressPrice(value=Decimal("10.00")),
            product_url="https://www.aliexpress.com/item/real_001.html",
            source="api",
        )
        assert product.is_mock is False

    def test_demo_label_mock(self, sample_product):
        assert "DEMO" in sample_product.demo_label

    def test_demo_label_real(self):
        product = AliExpressProduct(
            product_id="real_001",
            title="Real Product",
            price=AliExpressPrice(value=Decimal("10.00")),
            product_url="https://www.aliexpress.com/item/real_001.html",
            source="api",
        )
        assert product.demo_label == ""

    def test_to_dict_complete(self, sample_product):
        d = sample_product.to_dict()
        assert d["product_id"] == "ali_001"
        assert d["source"] == "mock"
        assert d["is_mock"] is True
        assert "DEMO" in d["demo_label"]
        assert d["rating_score"] == 4.8
        assert d["price"]["value"] == 8.99

    def test_to_db_dict(self, sample_product):
        d = sample_product.to_db_dict()
        assert d["product_id"] == "ali_001"
        assert d["price_value"] == Decimal("8.99")
        assert d["price_currency"] == "USD"
        assert d["store_name"] == "TechPro Store"
        assert d["source"] == "mock"

    def test_default_shipping_empty(self):
        product = AliExpressProduct(
            product_id="ali_minimal",
            title="Minimal Product",
            price=AliExpressPrice(value=Decimal("5.00")),
            product_url="https://www.aliexpress.com/item/minimal.html",
            source="mock",
        )
        assert product.shipping_options == []
        assert product.attributes == {}

    def test_fetched_at_default(self):
        product = AliExpressProduct(
            product_id="ali_time",
            title="Time Product",
            price=AliExpressPrice(value=Decimal("5.00")),
            product_url="https://www.aliexpress.com/item/time.html",
            source="mock",
        )
        assert isinstance(product.fetched_at, datetime)