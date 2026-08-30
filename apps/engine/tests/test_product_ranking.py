"""
Tests for ProductRankingService.
"""
from decimal import Decimal
from datetime import datetime

import pytest

from services.ranking import (
    ProductRankingService,
    RankedProduct,
    DemandLabel,
)


class TestProductRankingService:
    """Test product ranking logic."""

    @pytest.fixture
    def ranker(self):
        return ProductRankingService()

    def _listing(
        self,
        item_id="v1|001|0",
        title="Test Product",
        price=29.99,
        currency="USD",
        marketplace="EBAY_US",
        feedback_pct=98.0,
        feedback_score=1000,
        sold=None,
        buying_options=None,
        shipping_options=None,
        image_url="https://img.example.com/img.jpg",
        item_web_url="https://www.ebay.com/itm/001",
    ):
        """Build a minimal listing dict for testing."""
        return {
            "item_id": item_id,
            "title": title,
            "price_value": Decimal(str(price)),
            "price_currency": currency,
            "marketplace": marketplace,
            "image_url": image_url,
            "item_web_url": item_web_url,
            "condition": "New",
            "seller_username": "test_seller",
            "seller_feedback_percentage": feedback_pct,
            "seller_feedback_score": feedback_score,
            "estimated_sold_quantity": sold,
            "buying_options": buying_options if buying_options else ["FIXED_PRICE"],
            "shipping_options": (
                shipping_options
                if shipping_options is not None
                else [{"shippingCostType": "FREE"}]
            ),
        }

    # -------------------------------------------------------------------------
    # Basic behavior
    # -------------------------------------------------------------------------

    def test_rank_empty_listings(self, ranker):
        result = ranker.rank([])
        assert result == []

    def test_rank_returns_list(self, ranker):
        listings = [self._listing()]
        result = ranker.rank(listings)
        assert isinstance(result, list)
        assert all(isinstance(r, RankedProduct) for r in result)

    def test_ranks_are_sequential_starting_at_one(self, ranker):
        listings = [
            self._listing(item_id="v1|1|0"),
            self._listing(item_id="v1|2|0"),
            self._listing(item_id="v1|3|0"),
        ]
        result = ranker.rank(listings)
        assert [r.rank for r in result] == [1, 2, 3]

    def test_preserves_all_listing_fields(self, ranker):
        listing = self._listing(
            image_url="https://i.ebayimg.com/x.jpg",
            item_web_url="https://www.ebay.com/itm/xyz",
        )
        result = ranker.rank([listing])
        r = result[0]
        assert r.image_url == "https://i.ebayimg.com/x.jpg"
        assert r.item_web_url == "https://www.ebay.com/itm/xyz"
        assert r.price_value == Decimal("29.99")
        assert r.price_currency == "USD"
        assert r.marketplace == "EBAY_US"

    def test_original_listing_preserved(self, ranker):
        listing = self._listing()
        result = ranker.rank([listing])
        assert result[0].original_listing == listing

    # -------------------------------------------------------------------------
    # Deterministic ordering
    # -------------------------------------------------------------------------

    def test_higher_sold_ranks_higher(self, ranker):
        listings = [
            self._listing(item_id="v1|low|0", sold=5),
            self._listing(item_id="v1|high|0", sold=200),
            self._listing(item_id="v1|mid|0", sold=30),
        ]
        result = ranker.rank(listings)
        # Highest sold should be rank 1
        assert result[0].item_id == "v1|high|0"

    def test_sold_signal_beats_no_sold_signal(self, ranker):
        listings = [
            self._listing(item_id="v1|no_sold|0", sold=None, feedback_pct=99),
            self._listing(item_id="v1|has_sold|0", sold=100, feedback_pct=95),
        ]
        result = ranker.rank(listings)
        assert result[0].item_id == "v1|has_sold|0"

    def test_deterministic_output(self, ranker):
        listings = [
            self._listing(item_id=f"v1|item{i}|0", sold=i * 10)
            for i in range(1, 6)
        ]
        result_1 = ranker.rank(listings)
        result_2 = ranker.rank(listings)
        assert [r.item_id for r in result_1] == [r.item_id for r in result_2]

    def test_stable_tiebreaker_on_identical_scores(self, ranker):
        # Two listings with identical everything except item_id
        l1 = self._listing(item_id="v1|aaa|0", sold=None)
        l2 = self._listing(item_id="v1|bbb|0", sold=None)
        result = ranker.rank([l2, l1])  # deliberately reversed
        # Item IDs should be sorted ascending as tiebreaker
        # Both scores identical → deterministic order
        ids = [r.item_id for r in result]
        assert ids == sorted(ids)

    # -------------------------------------------------------------------------
    # Demand labels
    # -------------------------------------------------------------------------

    def test_top_selling_label_for_high_sold(self, ranker):
        listing = self._listing(sold=100)
        result = ranker.rank([listing])
        assert result[0].demand_label == DemandLabel.TOP_SELLING
        assert "100" in result[0].demand_reason

    def test_top_selling_at_threshold(self, ranker):
        listing = self._listing(sold=50)
        result = ranker.rank([listing])
        assert result[0].demand_label == DemandLabel.TOP_SELLING

    def test_high_demand_estimated_label(self, ranker):
        listing = self._listing(sold=25)
        result = ranker.rank([listing])
        assert result[0].demand_label == DemandLabel.HIGH_DEMAND_ESTIMATED
        assert "Estimated" in result[0].demand_label.value

    def test_some_demand_estimated_label(self, ranker):
        listing = self._listing(sold=3)
        result = ranker.rank([listing])
        assert result[0].demand_label == DemandLabel.SOME_DEMAND_ESTIMATED

    def test_high_market_interest_no_sold_data(self, ranker):
        # Many listings, good signals, no per-listing sold data
        listings = [
            self._listing(
                item_id=f"v1|{i}|0",
                sold=None,
                feedback_pct=99,
            )
            for i in range(1, 21)  # 20 listings for confidence
        ]
        result = ranker.rank(listings, total_available=500)
        # First result should be labeled by market interest, not sold
        # (all have identical no-sold-data pattern)
        for r in result:
            assert r.demand_label in [
                DemandLabel.HIGH_MARKET_INTEREST,
                DemandLabel.MODERATE_INTEREST,
                DemandLabel.LIMITED_DATA,
            ]
            assert not r.sold_signal_available

    def test_limited_data_label_low_signals(self, ranker):
        # Very few listings, no sold data → limited data
        listings = [self._listing(item_id="v1|solo|0", sold=None)]
        result = ranker.rank(listings)
        # Should not claim high demand
        assert result[0].demand_label in [
            DemandLabel.LIMITED_DATA,
            DemandLabel.MODERATE_INTEREST,
        ]

    def test_never_claims_top_selling_without_sold_data(self, ranker):
        """Critical: cannot say Top Selling without eBay sold quantity."""
        listings = [
            self._listing(
                item_id=f"v1|{i}|0",
                sold=None,  # never any sold data
                feedback_pct=100,  # perfect sellers
            )
            for i in range(50)
        ]
        result = ranker.rank(listings, total_available=10000)
        for r in result:
            assert r.demand_label != DemandLabel.TOP_SELLING

    # -------------------------------------------------------------------------
    # Confidence
    # -------------------------------------------------------------------------

    def test_high_confidence_when_sold_data_present(self, ranker):
        listing = self._listing(sold=100)
        result = ranker.rank([listing])
        assert result[0].confidence == "high"

    def test_low_confidence_no_sold_no_signals(self, ranker):
        # Very small sample, no sold data
        listing = self._listing(item_id="v1|1|0", sold=None)
        result = ranker.rank([listing])
        assert result[0].confidence in ["low", "medium"]

    # -------------------------------------------------------------------------
    # Ranking score properties
    # -------------------------------------------------------------------------

    def test_ranking_score_in_valid_range(self, ranker):
        listings = [self._listing(sold=100), self._listing(sold=None)]
        result = ranker.rank(listings)
        for r in result:
            assert 0 <= r.ranking_score <= 100

    def test_market_score_included_in_result(self, ranker):
        listings = [
            self._listing(item_id=f"v1|{i}|0") for i in range(1, 11)
        ]
        result = ranker.rank(listings, total_available=200)
        for r in result:
            assert 0 <= r.market_score <= 100

    # -------------------------------------------------------------------------
    # Missing / broken data resilience
    # -------------------------------------------------------------------------

    def test_missing_feedback_does_not_crash(self, ranker):
        listing = self._listing(feedback_pct=None, feedback_score=None)
        result = ranker.rank([listing])
        assert len(result) == 1

    def test_missing_shipping_does_not_crash(self, ranker):
        listing = self._listing(shipping_options=[])
        result = ranker.rank([listing])
        assert len(result) == 1

    def test_missing_buying_options_does_not_crash(self, ranker):
        listing = self._listing(buying_options=[])
        result = ranker.rank([listing])
        assert len(result) == 1

    def test_none_shipping_does_not_crash(self, ranker):
        listing = self._listing()
        listing["shipping_options"] = None
        result = ranker.rank([listing])
        assert len(result) == 1

    def test_none_buying_options_does_not_crash(self, ranker):
        listing = self._listing()
        listing["buying_options"] = None
        result = ranker.rank([listing])
        assert len(result) == 1

    def test_zero_sold_handled(self, ranker):
        listing = self._listing(sold=0)
        result = ranker.rank([listing])
        assert len(result) == 1
        assert result[0].sold_signal_available is True

    def test_invalid_feedback_string_handled(self, ranker):
        listing = self._listing(feedback_pct="not a number")
        result = ranker.rank([listing])
        assert len(result) == 1

    # -------------------------------------------------------------------------
    # to_dict serialization
    # -------------------------------------------------------------------------

    def test_to_dict_has_required_fields(self, ranker):
        listing = self._listing(sold=100)
        result = ranker.rank([listing])
        d = result[0].to_dict()

        required = [
            "rank",
            "item_id",
            "title",
            "price",
            "marketplace",
            "image_url",
            "item_web_url",
            "demand",
            "ranking_score",
            "market_score",
        ]
        for key in required:
            assert key in d, f"Missing: {key}"

    def test_to_dict_price_has_currency(self, ranker):
        listing = self._listing(price=45.50, currency="GBP")
        result = ranker.rank([listing])
        d = result[0].to_dict()
        assert d["price"]["value"] == 45.50
        assert d["price"]["currency"] == "GBP"

    def test_to_dict_demand_includes_evidence_flag(self, ranker):
        listing = self._listing(sold=100)
        result = ranker.rank([listing])
        d = result[0].to_dict()
        assert d["demand"]["sold_data_available"] is True
        assert d["demand"]["estimated_sold_quantity"] == 100