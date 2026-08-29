"""
Tests for scoring signal normalizers (Phase 7 Step 2).
"""
from decimal import Decimal
import pytest

from services.scoring.normalizers import (
    normalize_market_score,
    normalize_competition_score,
    normalize_margin,
    normalize_absolute_profit,
    normalize_roi,
    normalize_profit_score,
    normalize_match_score,
    calculate_policy_penalty,
)
from services.scoring.market_signals import MarketSignals
from services.scoring.competition_signals import CompetitionSignals
from services.profit.models import ProfitResult, FeeBreakdown
from services.matching.matcher import ProductMatchResult
from services.policy.models import PolicyAssessment, PolicyRiskLevel
from services.scoring.weights import EconomicsSubWeights, MatchSubWeights


def _make_market_signals(**kwargs) -> MarketSignals:
    defaults = {
        "overall_market_score": 85.5,
        "confidence": 0.9,
        "confidence_label": "High",
        "listing_activity_score": 80.0,
        "listing_activity_interpretation": "High",
        "listings_analyzed": 10,
        "total_available": 100,
        "mean_price": 50.0,
        "price_std_dev": 5.0,
        "price_coefficient_of_variation": 0.1,
        "price_stability_score": 80.0,
        "price_interpretation": "Stable",
        "seller_quality_score": 85.0,
        "avg_seller_feedback": 99.0,
        "seller_quality_interpretation": "Excellent",
        "estimated_sold_available": True,
        "total_estimated_sold": 100,
        "estimated_sold_signal": "High",
        "signals_available": ["test"],
        "signals_missing": [],
    }
    defaults.update(kwargs)
    return MarketSignals(**defaults)


def _make_competition_signals(**kwargs) -> CompetitionSignals:
    defaults = {
        "overall_competition_score": 30.0,
        "competition_level": "Low",
        "free_shipping_score": 30.0,
        "free_shipping_percentage": 30.0,
        "shipping_interpretation": "Low",
        "market_type_score": 30.0,
        "fixed_price_percentage": 80.0,
        "market_type_interpretation": "Fixed",
    }
    defaults.update(kwargs)
    return CompetitionSignals(**defaults)


class TestMarketNormalization:
    def test_market_passthrough(self):
        signals = _make_market_signals(overall_market_score=85.5)
        assert normalize_market_score(signals) == 85.5

    def test_market_empty_returns_zero(self):
        assert normalize_market_score(None) == 0.0

    def test_market_zero_listings_returns_zero(self):
        signals = _make_market_signals(
            overall_market_score=85.5,
            listings_analyzed=0,
        )
        assert normalize_market_score(signals) == 0.0


class TestCompetitionNormalization:
    def test_competition_inversion(self):
        signals = _make_competition_signals(overall_competition_score=30.0)
        assert normalize_competition_score(signals) == 70.0

    def test_competition_bounds(self):
        sig_high = _make_competition_signals(overall_competition_score=120.0)
        assert normalize_competition_score(sig_high) == 0.0

        sig_low = _make_competition_signals(overall_competition_score=-20.0)
        assert normalize_competition_score(sig_low) == 100.0

    def test_competition_empty_returns_zero(self):
        assert normalize_competition_score(None) == 0.0


class TestEconomicsNormalizationCurves:
    def test_normalize_margin(self):
        # Boundaries
        assert normalize_margin(-10.0) == 0.0
        assert normalize_margin(0.0) == 0.0
        assert normalize_margin(50.0) == 100.0
        assert normalize_margin(60.0) == 100.0

        # Linear interpolation points
        assert normalize_margin(25.0) == 60.0  # 20 + (25/50)*80 = 20 + 40 = 60
        assert normalize_margin(12.5) == 40.0  # 20 + 20 = 40

    def test_normalize_absolute_profit(self):
        # Boundaries
        assert normalize_absolute_profit(-5.0) == 0.0
        assert normalize_absolute_profit(0.0) == 0.0
        assert normalize_absolute_profit(20.0) == 100.0
        assert normalize_absolute_profit(25.0) == 100.0

        # Piecewise 1: 0 to 5
        assert normalize_absolute_profit(2.5) == 25.0  # 10 + (2.5/5)*30 = 25
        assert normalize_absolute_profit(5.0) == 40.0

        # Piecewise 2: 5 to 20
        assert normalize_absolute_profit(12.5) == 70.0  # 40 + (7.5/15)*60 = 70

    def test_normalize_roi(self):
        # Boundaries
        assert normalize_roi(-50.0) == 0.0
        assert normalize_roi(0.0) == 0.0
        assert normalize_roi(300.0) == 100.0
        assert normalize_roi(400.0) == 100.0

        # Linear points
        assert normalize_roi(150.0) == 55.0  # 10 + (150/300)*90 = 55


class TestProfitScoreNormalization:
    @pytest.fixture
    def sub_weights(self):
        return EconomicsSubWeights()

    def test_profitable_combination(self, sub_weights):
        result = ProfitResult(
            is_profitable=True,
            profit_margin=25.0,  # margin_score = 60.0
            net_profit_per_item=Decimal("5.0"),  # profit_score = 40.0
            roi=150.0,  # roi_score = 55.0
            fees=FeeBreakdown(),
        )
        score = normalize_profit_score(result, sub_weights)
        expected = (60.0 * 0.40) + (40.0 * 0.35) + (55.0 * 0.25)  # 24 + 14 + 13.75 = 51.75
        assert abs(score - expected) < 0.01

    def test_unprofitable_cap_applied(self, sub_weights):
        """Unprofitable transaction must be capped at 15.0."""
        result = ProfitResult(
            is_profitable=False,
            profit_margin=-10.0,  # 0
            net_profit_per_item=Decimal("-2.0"),  # 0
            roi=-5.0,  # 0
            fees=FeeBreakdown(),
        )
        score = normalize_profit_score(result, sub_weights)
        assert score == 0.0

        result_high_fake = ProfitResult(
            is_profitable=False,
            profit_margin=40.0,  # High margin but is_profitable False (fake anomaly)
            net_profit_per_item=Decimal("15.0"),
            roi=200.0,
            fees=FeeBreakdown(),
        )
        score_high = normalize_profit_score(result_high_fake, sub_weights)
        assert score_high == 15.0  # Capped at 15.0

    def test_empty_returns_zero(self, sub_weights):
        assert normalize_profit_score(None, sub_weights) == 0.0


class TestMatchScoreNormalization:
    @pytest.fixture
    def sub_weights_no_rating(self):
        """Weights matching standard execution without optional rating."""
        return MatchSubWeights(
            match_confidence=0.60,
            supplier_rating=0.0,
            attribute_similarity=0.40,
        )

    @pytest.fixture
    def sub_weights_with_rating(self):
        """Weights requiring dynamic proportional redistribution."""
        return MatchSubWeights(
            match_confidence=0.50,
            supplier_rating=0.30,
            attribute_similarity=0.20,
        )

    def test_match_normalization_no_redistribution(self, sub_weights_no_rating):
        result = ProductMatchResult(
            ebay_item_id="ebay",
            ali_product_id="ali",
            match_score=0.80,  # 80
            attribute_similarity=0.70,  # 70
        )
        score = normalize_match_score(result, sub_weights_no_rating)
        expected = (80 * 0.60) + (70 * 0.40)  # 48 + 28 = 76
        assert abs(score - expected) < 0.01

    def test_match_normalization_proportional_redistribution(
        self, sub_weights_with_rating
    ):
        result = ProductMatchResult(
            ebay_item_id="ebay",
            ali_product_id="ali",
            match_score=0.80,  # 80
            attribute_similarity=0.70,  # 70
        )
        score = normalize_match_score(result, sub_weights_with_rating)
        expected = (80.0 * 5 / 7) + (70.0 * 2 / 7)  # 57.142 + 20 = 77.142
        assert abs(score - expected) < 0.01

    def test_empty_returns_zero(self, sub_weights_no_rating):
        assert normalize_match_score(None, sub_weights_no_rating) == 0.0


class TestPolicyPenaltyMultiplier:
    def test_all_penalty_tiers(self):
        ass = PolicyAssessment(marketplace="DE", item_id="1", title="test")

        ass.overall_risk = PolicyRiskLevel.LOW
        assert calculate_policy_penalty(ass) == 1.0

        ass.overall_risk = PolicyRiskLevel.REVIEW_REQUIRED
        assert calculate_policy_penalty(ass) == 0.85

        ass.overall_risk = PolicyRiskLevel.MEDIUM
        assert calculate_policy_penalty(ass) == 0.65

        ass.overall_risk = PolicyRiskLevel.HIGH
        assert calculate_policy_penalty(ass) == 0.30

    def test_missing_assessment_no_penalty(self):
        assert calculate_policy_penalty(None) == 1.0