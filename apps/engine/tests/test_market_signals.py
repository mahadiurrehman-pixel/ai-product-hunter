"""
Tests for market signals analysis.
"""
import pytest
from services.scoring.market_signals import (
    MarketSignalsAnalyzer,
    MarketSignals,
)


class TestMarketSignalsAnalyzer:
    """Test market signals analysis."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return MarketSignalsAnalyzer()

    @pytest.fixture
    def sample_listings_complete(self):
        """Sample listings with all fields present."""
        return [
            {
                "price_value": 29.99,
                "seller_feedback_percentage": 98.5,
                "estimated_sold_quantity": 120,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            },
            {
                "price_value": 31.50,
                "seller_feedback_percentage": 99.2,
                "estimated_sold_quantity": 85,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FIXED"}],
            },
            {
                "price_value": 28.99,
                "seller_feedback_percentage": 97.8,
                "estimated_sold_quantity": 200,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            },
            {
                "price_value": 30.00,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": None,
                "buying_options": ["FIXED_PRICE", "BEST_OFFER"],
                "shipping_options": [{"shippingCostType": "CALCULATED"}],
            },
            {
                "price_value": 29.50,
                "seller_feedback_percentage": 99.0,
                "estimated_sold_quantity": None,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            },
        ]

    @pytest.fixture
    def sample_listings_minimal(self):
        """Sample listings with minimal fields (3 listings)."""
        return [
            {"price_value": 25.00},
            {"price_value": 30.00},
            {"price_value": 27.50},
        ]

    def test_analyze_empty_listings(self, analyzer):
        """Test handling of empty listings."""
        result = analyzer.analyze([])

        assert result.listings_analyzed == 0
        assert result.overall_market_score == 0.0
        assert result.confidence == 0.0
        assert "all" in result.signals_missing

    def test_analyze_complete_listings(self, analyzer, sample_listings_complete):
        """Test analysis with complete data."""
        result = analyzer.analyze(sample_listings_complete)

        assert result.listings_analyzed == 5
        assert 0 <= result.overall_market_score <= 100
        assert 0 <= result.confidence <= 1
        assert len(result.signals_available) > 0
        assert isinstance(result.signals_missing, list)

    def test_analyze_listing_activity_niche(self, analyzer):
        """Test niche market detection (low count)."""
        score, interp = analyzer._analyze_listing_activity(5)

        assert score == 20.0
        assert "Limited" in interp or "Niche" in interp

    def test_analyze_listing_activity_emerging(self, analyzer):
        """Test emerging market detection."""
        score, interp = analyzer._analyze_listing_activity(30)

        assert 20 < score < 60
        assert "Emerging" in interp or "Niche" in interp

    def test_analyze_listing_activity_established(self, analyzer):
        """Test established market detection."""
        score, interp = analyzer._analyze_listing_activity(100)

        assert 60 <= score <= 100
        assert "Established" in interp

    def test_analyze_listing_activity_saturated(self, analyzer):
        """Test saturated market detection.
        New bands: 5000+ = Saturated. Use 6000 to clearly exceed threshold.
        """
        score, interp = analyzer._analyze_listing_activity(6000)

        assert score < 80
        assert "Saturated" in interp

    def test_analyze_price_stability_stable(self, analyzer):
        """Test stable price detection."""
        listings = [
            {"price_value": 29.99},
            {"price_value": 30.00},
            {"price_value": 29.95},
            {"price_value": 30.05},
        ]

        score, stats, interp = analyzer._analyze_price_stability(listings)

        assert stats["cv"] < 0.15
        assert score > 70
        assert "Stable" in interp

    def test_analyze_price_stability_variable(self, analyzer):
        """Test variable price detection."""
        listings = [
            {"price_value": 20.00},
            {"price_value": 30.00},
            {"price_value": 40.00},
            {"price_value": 25.00},
        ]

        score, stats, interp = analyzer._analyze_price_stability(listings)

        assert stats["cv"] > 0.15
        assert "Variable" in interp or "Unstable" in interp

    def test_analyze_price_stability_insufficient_data(self, analyzer):
        """Test handling of insufficient price data."""
        listings = [
            {"price_value": 29.99},
            {"price_value": 30.00},
        ]

        score, stats, interp = analyzer._analyze_price_stability(listings)

        assert score == 50.0
        assert "Insufficient" in interp

    def test_analyze_price_stability_invalid_prices(self, analyzer):
        """Test handling of invalid prices."""
        listings = [
            {"price_value": "invalid"},
            {"price_value": None},
            {"price_value": -10},
            {"price_value": 0},
            {"price_value": 29.99},
        ]

        score, stats, interp = analyzer._analyze_price_stability(listings)

        assert stats["mean"] > 0

    def test_analyze_seller_quality_high(self, analyzer):
        """Test high seller quality detection."""
        listings = [
            {"seller_feedback_percentage": 98.0},
            {"seller_feedback_percentage": 99.0},
            {"seller_feedback_percentage": 97.5},
        ]

        score, avg_feedback, interp = analyzer._analyze_seller_quality(
            listings
        )

        assert avg_feedback >= 97
        assert score >= 80
        assert "High" in interp or "Good" in interp

    def test_analyze_seller_quality_mixed(self, analyzer):
        """Test mixed seller quality detection."""
        listings = [
            {"seller_feedback_percentage": 88.0},
            {"seller_feedback_percentage": 92.0},
            {"seller_feedback_percentage": 86.0},
        ]

        score, avg_feedback, interp = analyzer._analyze_seller_quality(
            listings
        )

        assert 85 <= avg_feedback < 95
        assert score < 100
        assert "Mixed" in interp or "Lower" in interp

    def test_analyze_seller_quality_missing_data(self, analyzer):
        """Test handling of missing seller data."""
        listings = [
            {"seller_feedback_percentage": None},
            {},
            {"seller_feedback_percentage": None},
        ]

        score, avg_feedback, interp = analyzer._analyze_seller_quality(
            listings
        )

        assert avg_feedback is None
        assert score == 50.0
        assert "No seller" in interp or "available" in interp

    def test_analyze_estimated_sold_available(self, analyzer):
        """Test sold quantity analysis when available."""
        listings = [
            {"estimated_sold_quantity": 100},
            {"estimated_sold_quantity": 50},
            {"estimated_sold_quantity": 75},
        ]

        score, available, total = analyzer._analyze_estimated_sold(listings)

        assert available is True
        assert total == 225
        assert score is not None
        assert 0 <= score <= 100

    def test_analyze_estimated_sold_missing(self, analyzer):
        """Test sold quantity analysis when missing."""
        listings = [
            {"estimated_sold_quantity": None},
            {},
            {"estimated_sold_quantity": None},
        ]

        score, available, total = analyzer._analyze_estimated_sold(listings)

        assert available is False
        assert total is None
        assert score is None

    def test_analyze_estimated_sold_partial(self, analyzer):
        """Test sold quantity when only some listings have it."""
        listings = [
            {"estimated_sold_quantity": 100},
            {"estimated_sold_quantity": None},
            {"estimated_sold_quantity": 50},
            {},
        ]

        score, available, total = analyzer._analyze_estimated_sold(listings)

        assert available is True
        assert total == 150
        assert score is not None

    def test_calculate_overall_score_all_signals(self, analyzer):
        """Test overall score with all signals available."""
        score = analyzer._calculate_overall_score(
            listing_score=80.0,
            price_score=70.0,
            seller_score=90.0,
            sold_score=85.0,
            sold_available=True,
        )

        expected = 80 * 0.25 + 70 * 0.25 + 90 * 0.25 + 85 * 0.25
        assert abs(score - expected) < 0.5

    def test_calculate_overall_score_missing_sold(self, analyzer):
        """Test overall score when sold data missing."""
        score = analyzer._calculate_overall_score(
            listing_score=80.0,
            price_score=70.0,
            seller_score=90.0,
            sold_score=None,
            sold_available=False,
        )

        expected = 80 * 0.35 + 70 * 0.35 + 90 * 0.30
        assert abs(score - expected) < 0.5

    def test_confidence_all_signals_small_sample(self, analyzer):
        """
        5 listings with all signals → low confidence (sample too small).
        sample_factor for 5-9 = 0.50. 4/4 signals → 0.50 * 1.0 = 0.50.
        No total_available → 10% penalty → 0.45.
        """
        listings = [
            {
                "price_value": 29.99,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": 50,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(5)
        ]
        result = analyzer.analyze(listings)
        # 5 listings → sample_factor 0.50, regardless of signals
        assert result.confidence <= 0.55
        assert result.confidence >= 0.40

    def test_confidence_partial_signals(self, analyzer, sample_listings_minimal):
        """
        3 listings, minimal fields → very low confidence.
        sample_factor 0.25, 2/4 signals → 0.25*0.5 = 0.125, minus penalty.
        """
        result = analyzer.analyze(sample_listings_minimal)

        assert result.confidence <= 0.30

    def test_signals_tracking(self, analyzer, sample_listings_complete):
        """Test that signals_available and signals_missing are tracked."""
        result = analyzer.analyze(sample_listings_complete)

        assert isinstance(result.signals_available, list)
        assert isinstance(result.signals_missing, list)
        assert "listing_activity" in result.signals_available
        assert "price_analysis" in result.signals_available

    # -------------------------------------------------------------------------
    # New tests: sample size confidence tiers
    # -------------------------------------------------------------------------

    def test_confidence_all_signals_large_sample(self, analyzer):
        """
        20 listings + total_available provided + all signals → 0.90.
        No penalty because total_available is given.
        """
        listings = [
            {
                "price_value": 29.99 + i * 0.10,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": 50,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for i in range(20)
        ]
        result = analyzer.analyze(listings, total_available=500)
        # 20 listings, all 4 signals, total provided → 0.90 * 1.0 = 0.90
        assert result.confidence == pytest.approx(0.90, abs=0.05)

    def test_confidence_zero_listings(self, analyzer):
        """Zero listings → zero confidence."""
        result = analyzer.analyze([])
        assert result.confidence == 0.0

    def test_confidence_three_listings(self, analyzer):
        """3 listings must not produce high confidence."""
        listings = [
            {
                "price_value": 29.99,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": 100,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(3)
        ]
        result = analyzer.analyze(listings)
        assert result.confidence < 0.40
        assert (
            "Very Low" in result.confidence_label
            or "Low" in result.confidence_label
        )

    def test_confidence_eight_listings(self, analyzer):
        """8 listings → low confidence tier."""
        listings = [
            {
                "price_value": 29.99,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": None,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(8)
        ]
        result = analyzer.analyze(listings)
        assert result.confidence <= 0.50
        assert result.confidence > 0.0

    def test_confidence_ten_listings(self, analyzer):
        """
        10 listings + total_available + all signals → 0.70 * 1.0 = 0.70.
        """
        listings = [
            {
                "price_value": 29.99,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": 50,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(10)
        ]
        result = analyzer.analyze(listings, total_available=200)
        assert result.confidence == pytest.approx(0.70, abs=0.05)
        assert "Moderate" in result.confidence_label

    def test_confidence_twenty_plus_listings(self, analyzer):
        """
        25 listings + total_available + all signals → 0.90 >= 0.85.
        """
        listings = [
            {
                "price_value": 29.99,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": 50,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(25)
        ]
        result = analyzer.analyze(listings, total_available=1000)
        assert result.confidence >= 0.85
        assert "Good" in result.confidence_label

    # -------------------------------------------------------------------------
    # New tests: total_available propagation
    # -------------------------------------------------------------------------

    def test_total_available_used_for_listing_activity(self, analyzer):
        """
        When total_available is provided, listing activity should score
        based on total_available, not len(listings).
        5100 total → Saturated Market, score < 80.
        """
        listings = [
            {"price_value": 29.99, "seller_feedback_percentage": 98.0}
            for _ in range(5)
        ]
        result = analyzer.analyze(listings, total_available=5100)

        assert result.listing_activity_score < 80
        assert "Saturated" in result.listing_activity_interpretation
        assert result.total_available == 5100
        assert result.listings_analyzed == 5
    def test_total_available_none_uses_retrieved_count(self, analyzer):
        """
        Without total_available, confidence is slightly lower (10% penalty).
        """
        listings = [
            {
                "price_value": 29.99,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": 50,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(20)
        ]
        result_with = analyzer.analyze(listings, total_available=100)
        result_without = analyzer.analyze(listings, total_available=None)

        assert result_without.confidence <= result_with.confidence
        assert "sample" in result_without.listing_activity_interpretation.lower()

    def test_total_available_small(self, analyzer):
        """total_available=5 means genuinely small market."""
        listings = [{"price_value": 29.99} for _ in range(5)]
        result = analyzer.analyze(listings, total_available=5)
        assert result.listing_activity_score == 20.0
        assert "Limited" in result.listing_activity_interpretation

    def test_total_available_moderate(self, analyzer):
        """total_available=100 means established market."""
        listings = [{"price_value": 29.99} for _ in range(20)]
        result = analyzer.analyze(listings, total_available=100)
        assert result.listing_activity_score > 60
        assert "Established" in result.listing_activity_interpretation

    def test_total_available_large(self, analyzer):
        """total_available=2000 means competitive market."""
        listings = [{"price_value": 29.99} for _ in range(20)]
        result = analyzer.analyze(listings, total_available=2000)
        assert "Competitive" in result.listing_activity_interpretation

    def test_listings_analyzed_always_reflects_retrieved(self, analyzer):
        """listings_analyzed should always show retrieved count, not total."""
        listings = [{"price_value": 29.99} for _ in range(10)]
        result = analyzer.analyze(listings, total_available=5000)
        assert result.listings_analyzed == 10
        assert result.total_available == 5000