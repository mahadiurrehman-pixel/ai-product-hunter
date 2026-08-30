"""
Tests for MatchToProfitAdapter (Phase 7 Step 4).
"""
from decimal import Decimal
import pytest

from services.marketplace import Marketplace
from services.matching.matcher import ProductMatchResult
from services.product_identity.models import ProductIdentity
from services.profit.models import (
    ProfitInput,
    StoreType,
    UKSellerType,
    DESellerType,
    AUStoreType,
    CAStoreType,
    SellerLevel,
    TaxType,
)
from services.scoring.adapter import MatchToProfitAdapter
from services.aliexpress.models import AliExpressProduct, AliExpressPrice


@pytest.fixture
def adapter():
    return MatchToProfitAdapter()


class TestMatchToProfitAdapter:
    def test_convert_with_explicit_dictionaries(self, adapter):
        match = ProductMatchResult(
            ebay_item_id="ebay_123",
            ali_product_id="ali_456",
            match_score=0.85,
        )
        ebay_listing = {
            "price_value": Decimal("49.99"),
            "category": "consumer_electronics",
            "subcategory": "earbuds",
        }
        ali_product = {
            "price_value": Decimal("12.50"),
        }

        profit_input = adapter.convert(
            match_result=match,
            marketplace="US",
            ebay_listing=ebay_listing,
            ali_product=ali_product,
            shipping_cost=Decimal("3.50"),
            shipping_charged=Decimal("5.00"),
            promoted_rate=5.0,
        )

        assert isinstance(profit_input, ProfitInput)
        assert profit_input.marketplace == "US"
        assert profit_input.currency == "USD"
        assert profit_input.sold_price == Decimal("49.99")
        assert profit_input.item_cost == Decimal("12.50")
        assert profit_input.shipping_cost == Decimal("3.50")
        assert profit_input.shipping_charged == Decimal("5.00")
        assert profit_input.promoted_rate == 5.0
        assert profit_input.category == "consumer_electronics"
        assert profit_input.subcategory == "earbuds"

    def test_convert_with_ali_product_model(self, adapter):
        match = ProductMatchResult(
            ebay_item_id="ebay_123",
            ali_product_id="ali_456",
            match_score=0.90,
        )
        ali_prod = AliExpressProduct(
            product_id="ali_456",
            title="TWS Earbuds",
            price=AliExpressPrice(value=Decimal("8.90")),
            product_url="https://aliexpress.com/item/1",
            source="mock",
        )
        ebay_listing = {"price_value": "29.95"}

        profit_input = adapter.convert(
            match_result=match,
            marketplace=Marketplace.DE,
            ebay_listing=ebay_listing,
            ali_product=ali_prod,
        )

        assert profit_input.marketplace == "DE"
        assert profit_input.currency == "EUR"
        assert profit_input.sold_price == Decimal("29.95")
        assert profit_input.item_cost == Decimal("8.90")

    def test_convert_with_product_identities(self, adapter):
        ebay_id = ProductIdentity(
            product_type="smartwatch",
            model_family="apple_watch",
        )
        ali_id = ProductIdentity(
            product_type="smartwatch",
        )
        match = ProductMatchResult(
            ebay_item_id="ebay_1",
            ali_product_id="ali_1",
            match_score=0.95,
            ebay_identity=ebay_id,
            ali_identity=ali_id,
        )

        profit_input = adapter.convert(
            match_result=match,
            marketplace="UK",
            ebay_listing={"price_value": "199.00"},
            ali_product={"price_value": "50.00"},
        )

        assert profit_input.marketplace == "UK"
        assert profit_input.currency == "GBP"
        assert profit_input.category == "smartwatch"
        assert profit_input.subcategory == "apple_watch"

    def test_convert_all_marketplaces_defaults(self, adapter):
        match = ProductMatchResult(ebay_item_id="1", ali_product_id="2")

        # UK
        uk_inp = adapter.convert(match, marketplace="UK")
        assert uk_inp.currency == "GBP"
        assert uk_inp.uk_seller_type == UKSellerType.BUSINESS

        # DE
        de_inp = adapter.convert(match, marketplace="DE")
        assert de_inp.currency == "EUR"
        assert de_inp.de_seller_type == DESellerType.COMMERCIAL

        # AU
        au_inp = adapter.convert(match, marketplace="AU")
        assert au_inp.currency == "AUD"
        assert au_inp.au_store_type == AUStoreType.NO_STORE

        # CA
        ca_inp = adapter.convert(match, marketplace="CA")
        assert ca_inp.currency == "CAD"
        assert ca_inp.ca_store_type == CAStoreType.NO_STORE

    def test_convert_fallback_to_zero(self, adapter):
        """When no price data is present, sold_price and item_cost default to 0."""
        match = ProductMatchResult(ebay_item_id="1", ali_product_id="2")
        profit_input = adapter.convert(match, marketplace="US")

        assert profit_input.sold_price == Decimal("0")
        assert profit_input.item_cost == Decimal("0")