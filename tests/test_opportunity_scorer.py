"""
Tests for opportunity scoring.
"""
import pytest
from services.scoring.opportunity_scorer import (
    OpportunityScorer,
    OpportunityScore,
)


class TestOpportunityScorer:
    """Test opportunity scoring integration."""

    @pytest.fixture
    def scorer(self):
        """Create scorer instance."""
        return OpportunityScorer()

    @pytest.fixture
    def good_opportunity_listings(self):
        """Listings indicating good opportunity."""
        return [
            {
                "price_value": 30.00,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": 100,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FIXED"}],
            }
            for _ in range(50)
        ]

    @pytest.fixture
    def saturated_market_listings(self):
        """Listings indicating saturated market."""
        return [
            {
                "price_value": 25.00,
                "seller_feedback_percentage": 99.0,
                "estimated_sold_quantity": 500,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(1500)
        ]

    @pytest.fixture
    def niche_opportunity_listings(self):
        """Listings indicating niche opportunity."""
        return [
            {
                "price_value": 50.00,
                "seller_feedback_percentage": 95.0,
                "estimated_sold_quantity": None,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "CALCULATED"}],
            }
            for _ in range(8)
        ]

    def test_score_empty_listings(self, scorer):
        """Test scoring with no listings."""
        result = scorer.score([])

        assert result.overall_score == 0.0
        assert result.confidence == 0.0
        assert result.listings_analyzed == 0
        assert "NO DATA" in result.recommendation

    def test_score_returns_valid_range(
        self, scorer, good_opportunity_listings
    ):
        """Test score is within valid range."""
        result = scorer.score(good_opportunity_listings)

        assert 0 <= result.overall_score <= 100
        assert 0 <= result.confidence <= 1

    def test_score_has_components(self, scorer, good_opportunity_listings):
        """Test score includes all components."""
        result = scorer.score(good_opportunity_listings)

        assert result.market_signals is not None
        assert result.competition_signals is not None
        assert isinstance(result.reasoning, list)
        assert len(result.reasoning) > 0

    def test_score_good_opportunity(self, scorer, good_opportunity_listings):
        """Test scoring of good opportunity."""
        result = scorer.score(good_opportunity_listings)

        # Moderate listings, decent signals
        assert result.overall_score > 40
        assert result.confidence > 0.5
        assert result.listings_analyzed == 50

    def test_score_saturated_market(
        self, scorer, saturated_market_listings
    ):
        """Test scoring of high-competition/large market."""
        result = scorer.score(saturated_market_listings)

        # High competition should be present (100% free shipping)
        assert result.competition_signals.overall_competition_score > 75
        # 1500 listings without total_available → Competitive market
        # (Saturated requires 5000+ with new real-scale bands)
        assert (
            "Competitive" in result.market_signals.listing_activity_interpretation
            or "Saturated" in result.market_signals.listing_activity_interpretation
        )
        
    def test_score_niche_opportunity(
        self, scorer, niche_opportunity_listings
    ):
        """Test scoring of niche opportunity."""
        result = scorer.score(niche_opportunity_listings)

        # Low listing count
        assert result.listings_analyzed == 8
        # Missing sold data should reduce confidence
        assert result.market_signals.estimated_sold_available is False

    def test_score_has_limitations(self, scorer, good_opportunity_listings):
        """Test that limitations are always stated."""
        result = scorer.score(good_opportunity_listings)

        assert len(result.limitations) > 0
        # Should mention it's based on analyzed listings
        assert any(
            "analyzed" in lim.lower() or "snapshot" in lim.lower()
            for lim in result.limitations
        )
        # Should mention not a guarantee
        assert any(
            "guarantee" in lim.lower() or "does not" in lim.lower()
            for lim in result.limitations
        )

    def test_score_signals_tracked(self, scorer, good_opportunity_listings):
        """Test that signals used are tracked."""
        result = scorer.score(good_opportunity_listings)

        assert len(result.signals_used) > 0
        assert "listing_activity" in result.signals_used
        assert "competition_analysis" in result.signals_used

    def test_score_missing_sold_signal_noted(
        self, scorer, niche_opportunity_listings
    ):
        """Test missing sold signal is documented."""
        result = scorer.score(niche_opportunity_listings)

        # Should note missing data
        assert "estimated_sold" in result.market_signals.signals_missing
        # Should have limitation about it
        assert any(
            "sold data unavailable" in lim.lower()
            for lim in result.limitations
        )

    def test_score_high_competition_reduces_opportunity(self, scorer):
        """Test that high competition reduces opportunity score."""
        listings = [
            {
                "price_value": 30.00,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": 100,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(50)
        ]

        result = scorer.score(listings)

        # 100% free shipping = high competition
        assert result.competition_signals.free_shipping_percentage == 100.0
        # This should reduce opportunity compared to low competition
        market_score = result.market_signals.overall_market_score
        comp_score = result.competition_signals.overall_competition_score
        # Overall should be lower than pure market score due to competition
        assert result.overall_score < market_score

    def test_recommendation_categories(self, scorer):
        """Test recommendation categories are appropriate."""
        # High score
        high_score_result = scorer._generate_recommendation(
            75.0,
            scorer.market_analyzer._empty_signals(),
            scorer.competition_analyzer._empty_signals(),
        )
        recommendation, _ = high_score_result
        assert "INVESTIGATE FURTHER" in recommendation or "Promising" in recommendation

        # Medium score
        med_score_result = scorer._generate_recommendation(
            55.0,
            scorer.market_analyzer._empty_signals(),
            scorer.competition_analyzer._empty_signals(),
        )
        recommendation, _ = med_score_result
        assert "CAUTION" in recommendation or "Mixed" in recommendation

        # Low score
        low_score_result = scorer._generate_recommendation(
            30.0,
            scorer.market_analyzer._empty_signals(),
            scorer.competition_analyzer._empty_signals(),
        )
        recommendation, _ = low_score_result
        assert "WEAK" in recommendation or "alternatives" in recommendation.lower()

    def test_reasoning_provides_context(
        self, scorer, good_opportunity_listings
    ):
        """Test reasoning provides actionable context."""
        result = scorer.score(good_opportunity_listings)

        # Should mention listing count
        assert any(
            str(result.listings_analyzed) in reason
            for reason in result.reasoning
        )
        # Should mention competition level
        assert any(
            "Competition" in reason or "🏆" in reason
            for reason in result.reasoning
        )

    def test_confidence_reflects_data_availability(self, scorer):
        """Test confidence is based on data availability, not profit certainty."""
        # All signals present
        complete_listings = [
            {
                "price_value": 30.00,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": 100,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(10)
        ]

        # Missing sold data
        incomplete_listings = [
            {
                "price_value": 30.00,
                "seller_feedback_percentage": 98.0,
                # No estimated_sold_quantity
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(10)
        ]

        complete_result = scorer.score(complete_listings)
        incomplete_result = scorer.score(incomplete_listings)

        # Complete data should have higher confidence
        assert complete_result.confidence > incomplete_result.confidence
    def test_score_accepts_total_available(self, scorer):
        """
        OpportunityScorer.score() should accept and propagate total_available.
        """
        listings = [
            {
                "price_value": 30.00,
                "seller_feedback_percentage": 98.0,
                "estimated_sold_quantity": 50,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(20)
        ]
        result = scorer.score(listings, total_available=5000)
        assert result.total_available == 5000
        assert result.listings_analyzed == 20
        assert "5000" in result.limitations[0] or "5000" in str(result.reasoning)

    def test_score_without_total_available(self, scorer):
        """
        Without total_available, system still works but notes limitation.
        """
        listings = [
            {
                "price_value": 30.00,
                "seller_feedback_percentage": 98.0,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(20)
        ]
        result = scorer.score(listings)
        assert result.total_available is None
        # Should note the limitation
        assert any(
            "total" in lim.lower() or "sample" in lim.lower()
            for lim in result.limitations
        )

    def test_score_confidence_label_present(self, scorer):
        """OpportunityScore should include confidence_label."""
        listings = [
            {
                "price_value": 30.00,
                "seller_feedback_percentage": 98.0,
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(20)
        ]
        result = scorer.score(listings)
        assert result.confidence_label is not None
        assert len(result.confidence_label) > 0