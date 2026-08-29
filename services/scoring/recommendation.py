"""
Opportunity recommendation classification engine.

Evaluates normalized scores, profitability indicators, and policy assessments
to generate deterministic, safety-guarded classifications.
"""
from enum import Enum
from typing import Optional

from services.policy.models import PolicyAssessment, PolicyRiskLevel
from services.scoring.weights import ScoringThresholds


class Recommendation(str, Enum):
    """Actionable opportunity recommendation classifications."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    AVOID = "avoid"
    HIGH_RISK = "high_risk"

    @property
    def label(self) -> str:
        labels = {
            Recommendation.STRONG_BUY: "🟢 STRONG BUY — Outstanding Opportunity",
            Recommendation.BUY: "🟢 BUY — Promising Opportunity",
            Recommendation.HOLD: "🟡 HOLD — Proceed with Caution / Mixed Signals",
            Recommendation.AVOID: "🔴 AVOID — Weak or Unprofitable Opportunity",
            Recommendation.HIGH_RISK: "⛔ HIGH RISK — Critical Policy or Sourcing Risk",
        }
        return labels[self]


def classify_recommendation(
    final_score: float,
    is_profitable: bool,
    policy_assessment: Optional[PolicyAssessment],
    thresholds: ScoringThresholds,
) -> Recommendation:
    """
    Classify an overall opportunity score with strict deterministic safety overrides.

    Classification Flow:
    1. Initial classification based on numeric score thresholds:
       - score >= excellent_score (80) -> STRONG_BUY
       - score >= good_score (65)      -> BUY
       - score >= moderate_score (50)  -> HOLD
       - score >= poor_score (35)      -> AVOID
       - score < poor_score (35)       -> HIGH_RISK

    2. Safety Overrides:
       - Policy Risk Level is HIGH -> Force HIGH_RISK (regardless of score).
       - Transaction is unprofitable -> Downgrade STRONG_BUY or BUY to HOLD.

    Args:
        final_score: Final calculated opportunity score (0.0 to 100.0)
        is_profitable: Whether the transaction yields positive net profit
        policy_assessment: Optional PolicyAssessment instance
        thresholds: ScoringThresholds boundary configuration

    Returns:
        Recommendation enum classification
    """
    # 1. Base classification from score
    if final_score >= thresholds.excellent_score:
        rec = Recommendation.STRONG_BUY
    elif final_score >= thresholds.good_score:
        rec = Recommendation.BUY
    elif final_score >= thresholds.moderate_score:
        rec = Recommendation.HOLD
    elif final_score >= thresholds.poor_score:
        rec = Recommendation.AVOID
    else:
        rec = Recommendation.HIGH_RISK

    # 2. Policy safety override: High policy risk forces HIGH_RISK
    if policy_assessment and policy_assessment.overall_risk == PolicyRiskLevel.HIGH:
        return Recommendation.HIGH_RISK

    # 3. Profitability safety override: Unprofitable sales cannot be recommended as BUY
    if not is_profitable and rec in (Recommendation.STRONG_BUY, Recommendation.BUY):
        return Recommendation.HOLD

    return rec