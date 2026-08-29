"""
Tests for Unified Opportunity Scorer Engine (Phase 7 Step 5).
"""
from decimal import Decimal
import pytest

from services.matching.matcher import ProductMatchResult
from services.policy.models import PolicyAssessment, PolicyRiskLevel
from services.profit.models import FeeBreakdown, ProfitResult
from services.scoring.competition_signals import CompetitionSignals
from services.scoring.market_signals import MarketSignals
from services.scoring.recommendation import Recommendation
from services.scoring.unified_scorer import UnifiedOpportunityScorer, UnifiedOpportunityScore
from services.scoring.weights import ScoringConfig, ScoringWeights, ScoringThresholds, EconomicsSubWeights, MatchSubWeights


def _make_market(score=80.0, conf=0.9):
    return MarketSignals(
        overall_market_score=score,
        confidence=conf,
        confidence_label="High",
        listing_activity_score=80.0,
        listing_activity_interpretation="High",
        listings_analyzed=10,
        total_available=100,
        mean_price=50.0,
        price_std_dev=5.0,
        price_coefficient_of_variation=0.1,
        price_stability_score=80.0,
        price_interpretation="Stable",
        seller_quality_score=85.0,
        avg_seller_feedback=99.0,
        seller_quality_interpretation="Excellent",
        estimated_sold_available=True,
        total_estimated_sold=100,
        estimated_sold_signal="High",
        signals_available=["test"],
        signals_missing=[],
    )


def _make_competition(comp_score=20.0):
    return CompetitionSignals(
        overall_competition_score=comp_score,
        competition_level="Low",
        free_shipping_score=30.0,
        free_shipping_percentage=30.0,
        shipping_interpretation="Low",
        market_type_score=30.0,
        fixed_price_percentage=80.0,
        market_type_interpretation="Fixed",
    )


def _make_profit(margin=30.0, net=10.0, roi=100.0, profitable=True, conf="high"):
    return ProfitResult(
        marketplace="US",
        currency="USD",
        sold_price=Decimal("50.00"),
        item_cost=Decimal("20.00"),
        shipping_cost=Decimal("5.00"),
        shipping_charged=Decimal("5.00"),
        is_profitable=profitable,
        profit_margin=margin,
        net_profit_per_item=Decimal(str(net)),
        roi=roi,
        confidence=conf,
        fees=FeeBreakdown(total_fees=Decimal("15.00")),
    )


def _make_match(score=0.85, conf=0.85, attr_sim=0.80, match_type="very_similar"):
    return ProductMatchResult(
        ebay_item_id="ebay_1",
        ali_product_id="ali_1",
        match_score=score,
        confidence=conf,
        attribute_similarity=attr_sim,
        match_type=match_type,
    )


@pytest.fixture
def scorer():
    return UnifiedOpportunityScorer()


class TestUnifiedScorerCore:
    def test_strong_opportunity_scores_high(self, scorer):
        """High demand, low competition, great margin, strong match -> STRONG_BUY."""
        market = _make_market(score=85.0)
        comp = _make_competition(comp_score=15.0)  # Inverted -> 85.0
        profit = _make_profit(margin=45.0, net=25.0, roi=200.0)
        match = _make_match(score=0.95, attr_sim=0.90)
        policy = PolicyAssessment(marketplace="US", item_id="1", title="test", overall_risk=PolicyRiskLevel.LOW)

        score = scorer.score(market, comp, profit, match, policy)

        assert isinstance(score, UnifiedOpportunityScore)
        assert score.final_score >= 80.0
        assert score.recommendation == Recommendation.STRONG_BUY
        assert score.confidence == "high"
        assert score.policy_penalty == 1.0
        assert len(score.reasoning) >= 4

    def test_weak_opportunity_scores_low(self, scorer):
        """Poor signals across all components -> AVOID or HIGH_RISK."""
        market = _make_market(score=20.0)
        comp = _make_competition(comp_score=90.0)  # Inverted -> 10.0
        profit = _make_profit(margin=5.0, net=1.0, roi=10.0, profitable=True)
        match = _make_match(score=0.30, attr_sim=0.20, match_type="unlikely")
        policy = PolicyAssessment(marketplace="US", item_id="1", title="test", overall_risk=PolicyRiskLevel.LOW)

        score = scorer.score(market, comp, profit, match, policy)

        assert score.final_score < 35.0
        assert score.recommendation == Recommendation.HIGH_RISK

    def test_unprofitable_safety_override(self, scorer):
        """Unprofitable transaction downgrades recommendation to HOLD."""
        market = _make_market(score=90.0)
        comp = _make_competition(comp_score=10.0)
        profit = _make_profit(margin=-10.0, net=-5.0, roi=-20.0, profitable=False)
        match = _make_match(score=0.90, attr_sim=0.85)

        score = scorer.score(market, comp, profit, match, None)

        # Unprofitable cap limits economics to 15.0 max
        assert score.economics_score <= 15.0
        # Recommendation cannot be STRONG_BUY or BUY
        assert score.recommendation in (Recommendation.HOLD, Recommendation.AVOID)

    def test_policy_high_risk_penalty_and_override(self, scorer):
        """High policy risk severely penalizes score (0.30x) and forces HIGH_RISK."""
        market = _make_market(score=90.0)
        comp = _make_competition(comp_score=10.0)
        profit = _make_profit(margin=50.0, net=30.0, roi=250.0)
        match = _make_match(score=0.95, attr_sim=0.95)
        policy_high = PolicyAssessment(
            marketplace="US", item_id="1", title="test", overall_risk=PolicyRiskLevel.HIGH
        )

        score = scorer.score(market, comp, profit, match, policy_high)

        assert score.policy_penalty == 0.30
        assert score.final_score == pytest.approx(score.raw_weighted_score * 0.30, rel=1e-2)
        assert score.recommendation == Recommendation.HIGH_RISK
        assert any("High policy risk" in w for w in score.warnings)

    def test_policy_review_required_penalty(self, scorer):
        """Review required reduces final score by 15% (0.85x multiplier)."""
        market = _make_market(score=80.0)
        comp = _make_competition(comp_score=20.0)
        profit = _make_profit(margin=30.0, net=10.0, roi=100.0)
        match = _make_match(score=0.80, attr_sim=0.80)
        policy_rev = PolicyAssessment(
            marketplace="US", item_id="1", title="test", overall_risk=PolicyRiskLevel.REVIEW_REQUIRED
        )

        score = scorer.score(market, comp, profit, match, policy_rev)

        assert score.policy_penalty == 0.85
        assert score.final_score == pytest.approx(score.raw_weighted_score * 0.85, rel=1e-2)

    def test_missing_policy_safe_fallback(self, scorer):
        """None policy assessment applies 1.0x penalty with assumption log."""
        market = _make_market()
        comp = _make_competition()
        profit = _make_profit()
        match = _make_match()

        score = scorer.score(market, comp, profit, match, None)

        assert score.policy_penalty == 1.0
        assert score.policy_risk_level == "not_checked"
        assert any("Policy check not provided" in a for a in score.assumptions)

    def test_determinism(self, scorer):
        """Scorer execution must be 100% deterministic (same input -> same output)."""
        market = _make_market()
        comp = _make_competition()
        profit = _make_profit()
        match = _make_match()
        policy = PolicyAssessment(marketplace="US", item_id="1", title="test", overall_risk=PolicyRiskLevel.LOW)

        scores = [scorer.score(market, comp, profit, match, policy).final_score for _ in range(50)]
        assert len(set(scores)) == 1

    def test_to_dict_serialization(self, scorer):
        market = _make_market()
        comp = _make_competition()
        profit = _make_profit()
        match = _make_match()

        score = scorer.score(market, comp, profit, match, None)
        d = score.to_dict()

        assert "final_score" in d
        assert "recommendation" in d
        assert "component_scores" in d
        assert "policy" in d
        assert "weights_used" in d
        assert "reasoning" in d
        assert d["component_scores"]["market"] == pytest.approx(score.market_score, rel=1e-2)