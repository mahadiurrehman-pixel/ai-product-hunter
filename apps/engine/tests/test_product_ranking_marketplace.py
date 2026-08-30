"""
Tests for ProductRankingService with multi-marketplace and currency.
"""
from decimal import Decimal

import pytest

from services.ranking import ProductRankingService, DemandLabel


class TestRankingAcrossMarketplaces:
    """Test ranking works correctly with different marketplaces/currencies."""

    @pytest.fixture
    def ranker(self):
        return ProductRankingService()

    def _listing_for_market(
        self,
        item_id,
        marketplace,
        currency,
        price,
        sold=None,
        feedback_pct=98,
    ):
        return {
            "item_id": item_id,
            "title": f"Product {item_id}",
            "price_value": Decimal(str(price)),
            "price_currency": currency,
            "marketplace": marketplace,
            "image_url": "https://x.jpg",
            "item_web_url": "https://x.com",
            "condition": "New",
            "seller_username": "s",
            "seller_feedback_percentage": feedback_pct,
            "seller_feedback_score": 100,
            "estimated_sold_quantity": sold,
            "buying_options": ["FIXED_PRICE"],
            "shipping_options": [{"shippingCostType": "FREE"}],
        }

    def test_ranks_us_marketplace(self, ranker):
        listings = [
            self._listing_for_market("v1|us1|0", "EBAY_US", "USD", 29.99, sold=100),
        ]
        result = ranker.rank(listings)
        assert result[0].marketplace == "EBAY_US"
        assert result[0].price_currency == "USD"

    def test_ranks_uk_marketplace(self, ranker):
        listings = [
            self._listing_for_market("v1|uk1|0", "EBAY_GB", "GBP", 19.99, sold=50),
        ]
        result = ranker.rank(listings)
        assert result[0].marketplace == "EBAY_GB"
        assert result[0].price_currency == "GBP"

    def test_ranks_germany_marketplace(self, ranker):
        listings = [
            self._listing_for_market("v1|de1|0", "EBAY_DE", "EUR", 25.00, sold=75),
        ]
        result = ranker.rank(listings)
        assert result[0].marketplace == "EBAY_DE"
        assert result[0].price_currency == "EUR"

    def test_ranks_australia_marketplace(self, ranker):
        listings = [
            self._listing_for_market("v1|au1|0", "EBAY_AU", "AUD", 45.00, sold=30),
        ]
        result = ranker.rank(listings)
        assert result[0].marketplace == "EBAY_AU"
        assert result[0].price_currency == "AUD"

    def test_ranks_canada_marketplace(self, ranker):
        listings = [
            self._listing_for_market("v1|ca1|0", "EBAY_CA", "CAD", 39.99, sold=60),
        ]
        result = ranker.rank(listings)
        assert result[0].marketplace == "EBAY_CA"
        assert result[0].price_currency == "CAD"

    def test_price_not_used_for_ranking(self, ranker):
        """
        Critical: raw price must never be a ranking factor.
        Cheap product with better signals should outrank expensive one.
        """
        listings = [
            self._listing_for_market(
                "v1|expensive|0", "EBAY_US", "USD", 999.99,
                sold=5, feedback_pct=95,
            ),
            self._listing_for_market(
                "v1|cheap|0", "EBAY_US", "USD", 9.99,
                sold=200, feedback_pct=99,
            ),
        ]
        result = ranker.rank(listings)
        # Cheap product with better sold+seller signals should rank first
        assert result[0].item_id == "v1|cheap|0"

    def test_expensive_high_sold_beats_cheap_no_sold(self, ranker):
        """When sold signal available for one, it wins regardless of price."""
        listings = [
            self._listing_for_market(
                "v1|has_sold|0", "EBAY_US", "USD", 999.99, sold=100
            ),
            self._listing_for_market(
                "v1|no_sold|0", "EBAY_US", "USD", 9.99, sold=None
            ),
        ]
        result = ranker.rank(listings)
        assert result[0].item_id == "v1|has_sold|0"

    def test_never_compares_prices_across_currencies_numerically(self, ranker):
        """
        Same signals different currencies — ranking must not use raw price.
        £19.99 and $29.99 should tie on non-price factors, not be compared.
        """
        listings = [
            self._listing_for_market(
                "v1|us|0", "EBAY_US", "USD", 29.99,
                sold=100, feedback_pct=99,
            ),
            self._listing_for_market(
                "v1|uk|0", "EBAY_GB", "GBP", 19.99,
                sold=100, feedback_pct=99,
            ),
        ]
        result = ranker.rank(listings)
        # Identical ranking scores — tiebreaker on item_id
        assert result[0].ranking_score == pytest.approx(
            result[1].ranking_score, abs=0.01
        )

    def test_multiple_marketplaces_in_single_ranking(self, ranker):
        """Ranking works when listings span multiple marketplaces."""
        listings = [
            self._listing_for_market(
                "v1|us|0", "EBAY_US", "USD", 29.99, sold=200
            ),
            self._listing_for_market(
                "v1|uk|0", "EBAY_GB", "GBP", 19.99, sold=50
            ),
            self._listing_for_market(
                "v1|de|0", "EBAY_DE", "EUR", 25.00, sold=15
            ),
        ]
        result = ranker.rank(listings)
        # All 3 marketplaces present
        marketplaces = {r.marketplace for r in result}
        assert marketplaces == {"EBAY_US", "EBAY_GB", "EBAY_DE"}
        # Highest sold ranked first
        assert result[0].item_id == "v1|us|0"


class TestRankingImageAndUrlPreservation:
    """Test that image and listing URLs survive ranking."""

    @pytest.fixture
    def ranker(self):
        return ProductRankingService()

    def test_image_url_preserved(self, ranker):
        listing = {
            "item_id": "v1|img|0",
            "title": "Test",
            "price_value": Decimal("29.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
            "image_url": "https://i.ebayimg.com/images/g/abc/s-l1600.jpg",
            "item_web_url": "https://www.ebay.com/itm/img",
            "seller_feedback_percentage": 98,
            "estimated_sold_quantity": None,
            "buying_options": ["FIXED_PRICE"],
            "shipping_options": [{"shippingCostType": "FREE"}],
        }
        result = ranker.rank([listing])
        assert result[0].image_url == "https://i.ebayimg.com/images/g/abc/s-l1600.jpg"

    def test_listing_url_preserved(self, ranker):
        listing = {
            "item_id": "v1|url|0",
            "title": "Test",
            "price_value": Decimal("29.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
            "image_url": None,
            "item_web_url": "https://www.ebay.com/itm/preserved_url_123",
            "seller_feedback_percentage": 98,
            "estimated_sold_quantity": None,
            "buying_options": ["FIXED_PRICE"],
            "shipping_options": [],
        }
        result = ranker.rank([listing])
        assert result[0].item_web_url == "https://www.ebay.com/itm/preserved_url_123"

    def test_missing_image_url_gives_none_not_error(self, ranker):
        listing = {
            "item_id": "v1|noimg|0",
            "title": "Test",
            "price_value": Decimal("10.00"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
            "image_url": None,
            "item_web_url": "https://x.com",
            "seller_feedback_percentage": 95,
            "estimated_sold_quantity": None,
            "buying_options": ["FIXED_PRICE"],
            "shipping_options": [],
        }
        result = ranker.rank([listing])
        assert result[0].image_url is None