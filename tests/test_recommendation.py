"""
Tests for opportunity recommendation classification (Phase 7 Step 3).
"""
import pytest

from services.scoring.recommendation import Recommendation, classify_recommendation
from services.scoring.weights import ScoringThresholds
from services.policy.models import PolicyAssessment, PolicyRiskLevel


@pytest.fixture
def thresholds():
    return ScoringThresholds()


class TestRecommendationClassification:
    def test_threshold_ranges(self, thresholds):
        # Base ranges with profitable items and low policy risk
        policy = PolicyAssessment(marketplace="US", item_id="1", title="test", overall_risk=PolicyRiskLevel.LOW)

        assert classify_recommendation(85.0, True, policy, thresholds) == Recommendation.STRONG_BUY
        assert classify_recommendation(80.0, True, policy, thresholds) == Recommendation.STRONG_BUY
        assert classify_recommendation(75.0, True, policy, thresholds) == Recommendation.BUY
        assert classify_recommendation(65.0, True, policy, thresholds) == Recommendation.BUY
        assert classify_recommendation(55.0, True, policy, thresholds) == Recommendation.HOLD
        assert classify_recommendation(50.0, True, policy, thresholds) == Recommendation.HOLD
        assert classify_recommendation(45.0, True, policy, thresholds) == Recommendation.AVOID
        assert classify_recommendation(35.0, True, policy, thresholds) == Recommendation.AVOID
        assert classify_recommendation(20.0, True, policy, thresholds) == Recommendation.HIGH_RISK

    def test_high_policy_risk_override(self, thresholds):
        """High policy risk must unconditionally force HIGH_RISK."""
        policy_high = PolicyAssessment(
            marketplace="US", item_id="1", title="test", overall_risk=PolicyRiskLevel.HIGH
        )
        # Even with a perfect 100.0 score and profitable economics
        rec = classify_recommendation(100.0, True, policy_high, thresholds)
        assert rec == Recommendation.HIGH_RISK

    def test_unprofitable_downgrade_override(self, thresholds):
        """Unprofitable transactions cannot receive BUY recommendations."""
        policy_low = PolicyAssessment(
            marketplace="US", item_id="1", title="test", overall_risk=PolicyRiskLevel.LOW
        )

        # 90.0 score but unprofitable -> Downgraded to HOLD
        assert classify_recommendation(90.0, False, policy_low, thresholds) == Recommendation.HOLD

        # 70.0 score but unprofitable -> Downgraded to HOLD
        assert classify_recommendation(70.0, False, policy_low, thresholds) == Recommendation.HOLD

        # 40.0 score and unprofitable -> Remains AVOID
        assert classify_recommendation(40.0, False, policy_low, thresholds) == Recommendation.AVOID

    def test_none_policy_assessment(self, thresholds):
        """Missing policy assessment should not crash and apply basic classification."""
        rec = classify_recommendation(85.0, True, None, thresholds)
        assert rec == Recommendation.STRONG_BUY

    def test_labels_exist(self):
        for rec in Recommendation:
            assert isinstance(rec.label, str)
            assert len(rec.label) > 0