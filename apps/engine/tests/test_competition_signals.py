"""
Tests for competition signals analysis.
"""
import pytest
from services.scoring.competition_signals import (
    CompetitionSignalsAnalyzer,
    CompetitionSignals,
)


class TestCompetitionSignalsAnalyzer:
    """Test competition signals analysis."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return CompetitionSignalsAnalyzer()

    @pytest.fixture
    def high_competition_listings(self):
        """Listings indicating high competition."""
        return [
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            },
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            },
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            },
        ]

    @pytest.fixture
    def low_competition_listings(self):
        """Listings indicating lower competition."""
        return [
            {
                "buying_options": ["AUCTION"],
                "shipping_options": [{"shippingCostType": "FIXED"}],
            },
            {
                "buying_options": ["AUCTION"],
                "shipping_options": [{"shippingCostType": "CALCULATED"}],
            },
        ]

    def test_analyze_empty_listings(self, analyzer):
        """Test handling of empty listings."""
        result = analyzer.analyze([])

        assert result.overall_competition_score == 0.0
        assert result.free_shipping_percentage == 0.0
        assert result.fixed_price_percentage == 0.0
        assert result.competition_level == "Unknown"

    def test_analyze_high_competition(
        self, analyzer, high_competition_listings
    ):
        """Test high competition detection."""
        result = analyzer.analyze(high_competition_listings)

        # All have fixed price and free shipping
        assert result.free_shipping_percentage == 100.0
        assert result.fixed_price_percentage == 100.0
        assert result.overall_competition_score > 75

    def test_analyze_low_competition(
        self, analyzer, low_competition_listings
    ):
        """Test low competition detection."""
        result = analyzer.analyze(low_competition_listings)

        # Auction-heavy, no free shipping
        assert result.free_shipping_percentage == 0.0
        assert result.fixed_price_percentage == 0.0
        assert result.overall_competition_score < 50

    def test_analyze_shipping_high_free_shipping(self, analyzer):
        """Test high free shipping detection."""
        listings = [
            {"shipping_options": [{"shippingCostType": "FREE"}]},
            {"shipping_options": [{"shippingCostType": "FREE"}]},
            {"shipping_options": [{"shippingCostType": "FIXED"}]},
        ]

        score, pct, interp = analyzer._analyze_shipping(listings)

        assert pct > 60  # 2/3 = 66.67%
        assert score > 70
        assert "Competitive" in interp or "High" in interp

    def test_analyze_shipping_low_free_shipping(self, analyzer):
        """Test low free shipping detection."""
        listings = [
            {"shipping_options": [{"shippingCostType": "FIXED"}]},
            {"shipping_options": [{"shippingCostType": "CALCULATED"}]},
            {"shipping_options": [{"shippingCostType": "FIXED"}]},
        ]

        score, pct, interp = analyzer._analyze_shipping(listings)

        assert pct == 0.0
        assert score < 50

    def test_analyze_shipping_missing_options(self, analyzer):
        """Test handling of missing shipping options."""
        listings = [
            {"shipping_options": None},
            {},
            {"shipping_options": []},
        ]

        score, pct, interp = analyzer._analyze_shipping(listings)

        assert pct == 0.0

    def test_analyze_market_type_fixed_price(self, analyzer):
        """Test fixed price market detection."""
        listings = [
            {"buying_options": ["FIXED_PRICE"]},
            {"buying_options": ["FIXED_PRICE"]},
            {"buying_options": ["FIXED_PRICE", "BEST_OFFER"]},
        ]

        score, pct, interp = analyzer._analyze_market_type(listings)

        assert pct == 100.0
        assert score == 100.0
        assert "Retail" in interp or "Fixed Price" in interp

    def test_analyze_market_type_auction(self, analyzer):
        """Test auction market detection."""
        listings = [
            {"buying_options": ["AUCTION"]},
            {"buying_options": ["AUCTION"]},
            {"buying_options": ["AUCTION"]},
        ]

        score, pct, interp = analyzer._analyze_market_type(listings)

        assert pct == 0.0
        assert score < 50
        assert "Auction" in interp

    def test_analyze_market_type_mixed(self, analyzer):
        """Test mixed market detection."""
        listings = [
            {"buying_options": ["FIXED_PRICE"]},
            {"buying_options": ["AUCTION"]},
            {"buying_options": ["FIXED_PRICE"]},
            {"buying_options": ["AUCTION"]},
        ]

        score, pct, interp = analyzer._analyze_market_type(listings)

        assert pct == 50.0
        assert 40 < score < 80

    def test_competition_level_very_high(self, analyzer):
        """Test very high competition level assignment."""
        listings = [
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(10)
        ]

        result = analyzer.analyze(listings)

        assert result.overall_competition_score >= 75
        assert "Very High" in result.competition_level

    def test_competition_level_low(self, analyzer):
        """Test low competition level assignment."""
        listings = [
            {
                "buying_options": ["AUCTION"],
                "shipping_options": [{"shippingCostType": "CALCULATED"}],
            }
            for _ in range(10)
        ]

        result = analyzer.analyze(listings)

        assert result.overall_competition_score < 40
        assert "Low" in result.competition_level
    def test_recalibrated_moderate_free_shipping(self, analyzer):
        """
        50% free shipping should NOT be 'Very High Competition'
        after recalibration. Should be High or Moderate.
        """
        listings = [
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(5)
        ] + [
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FIXED"}],
            }
            for _ in range(5)
        ]
        result = analyzer.analyze(listings)
        # 50% free shipping should not be "Very High"
        assert "Very High" not in result.competition_level

    def test_recalibrated_high_free_shipping(self, analyzer):
        """
        70%+ free shipping should score as Very High Competition.
        """
        listings = [
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(8)
        ] + [
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FIXED"}],
            }
            for _ in range(2)
        ]
        result = analyzer.analyze(listings)
        # 80% free shipping → should be High or Very High
        assert result.free_shipping_percentage == 80.0
        assert result.overall_competition_score >= 65

    def test_recalibrated_normal_retail_not_very_high(self, analyzer):
        """
        Normal retail scenario (60% free shipping, 90% fixed price)
        should NOT score as 'Very High Competition' after recalibration.
        """
        listings = [
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(6)
        ] + [
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FIXED"}],
            }
            for _ in range(3)
        ] + [
            {
                "buying_options": ["AUCTION"],
                "shipping_options": [{"shippingCostType": "CALCULATED"}],
            }
            for _ in range(1)
        ]
        result = analyzer.analyze(listings)
        # 60% free shipping, 90% fixed price — normal retail
        # Should be High but NOT Very High
        assert "Very High" not in result.competition_level

    def test_recalibrated_low_competition_scenario(self, analyzer):
        """
        Low free shipping + mixed auction should score as Low competition.
        """
        listings = [
            {
                "buying_options": ["AUCTION"],
                "shipping_options": [{"shippingCostType": "FIXED"}],
            }
            for _ in range(7)
        ] + [
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "CALCULATED"}],
            }
            for _ in range(3)
        ]
        result = analyzer.analyze(listings)
        assert "Low" in result.competition_level

    def test_recalibrated_very_high_only_at_extreme(self, analyzer):
        """
        'Very High Competition' should only fire at genuinely
        extreme indicators: 80%+ free shipping, 80%+ fixed price.
        """
        listings = [
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FREE"}],
            }
            for _ in range(9)
        ] + [
            {
                "buying_options": ["FIXED_PRICE"],
                "shipping_options": [{"shippingCostType": "FIXED"}],
            }
            for _ in range(1)
        ]
        result = analyzer.analyze(listings)
        # 90% free shipping, 100% fixed price
        assert result.free_shipping_percentage == 90.0
        assert "Very High" in result.competition_level