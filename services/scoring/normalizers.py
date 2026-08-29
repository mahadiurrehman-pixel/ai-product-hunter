"""
Scoring signal normalizers.

Translates distinct multi-dimensional signals (Market, Competition, Economics,
Match Quality, Policy Risk) into normalized 0-100 score components and multipliers.
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Optional, Union

from services.scoring.market_signals import MarketSignals
from services.scoring.competition_signals import CompetitionSignals
from services.profit.models import ProfitResult
from services.policy.models import PolicyAssessment, PolicyRiskLevel
from services.scoring.weights import EconomicsSubWeights, MatchSubWeights

if TYPE_CHECKING:
    from services.matching.matcher import ProductMatchResult


def normalize_market_score(signals: Optional[MarketSignals]) -> float:
    """
    Normalize market/demand signals to a 0-100 scale.

    Since MarketSignalsAnalyzer already produces a normalized overall_market_score (0-100),
    this is a direct passthrough.

    Args:
        signals: MarketSignals instance from MarketSignalsAnalyzer

    Returns:
        Normalized market score (0.0 to 100.0)
    """
    if not signals or getattr(signals, "listings_analyzed", 0) == 0:
        return 0.0
    return float(signals.overall_market_score)


def normalize_competition_score(signals: Optional[CompetitionSignals]) -> float:
    """
    Normalize competition signals to a 0-100 scale.

    Inverts the competition score so that higher scores represent
    better opportunities (i.e., lower competition).

    Args:
        signals: CompetitionSignals instance from CompetitionSignalsAnalyzer

    Returns:
        Normalized competition opportunity score (0.0 to 100.0)
    """
    if not signals:
        return 0.0
    # High competition = low opportunity
    score = 100.0 - float(signals.overall_competition_score)
    return max(0.0, min(100.0, score))


def normalize_margin(margin_pct: float) -> float:
    """
    Map profit margin % to a 0-100 scale.

    Curves:
    - Negative or zero margin -> 0.0
    - Margin >= 50% -> 100.0
    - 0% < margin < 50% -> Linear interpolation from 20.0 to 100.0.
    """
    if margin_pct <= 0:
        return 0.0
    if margin_pct >= 50.0:
        return 100.0
    return 20.0 + (margin_pct / 50.0) * 80.0


def normalize_absolute_profit(net_profit: Union[Decimal, float, int]) -> float:
    """
    Map absolute net profit per item to a 0-100 scale.

    Curves:
    - Net profit <= 0 -> 0.0
    - Net profit >= $20 -> 100.0
    - Piecewise linear interpolation:
      - $0 < profit <= $5: linear from 10.0 to 40.0
      - $5 < profit < $20: linear from 40.0 to 100.0
    """
    profit = float(net_profit)
    if profit <= 0:
        return 0.0
    if profit >= 20.0:
        return 100.0
    if profit <= 5.0:
        return 10.0 + (profit / 5.0) * 30.0
    return 40.0 + ((profit - 5.0) / 15.0) * 60.0


def normalize_roi(roi_pct: float) -> float:
    """
    Map Return on Investment (ROI) % to a 0-100 scale.

    Curves:
    - ROI <= 0% -> 0.0
    - ROI >= 300% -> 100.0
    - 0% < ROI < 300% -> Linear interpolation from 10.0 to 100.0.
    """
    if roi_pct <= 0:
        return 0.0
    if roi_pct >= 300.0:
        return 100.0
    return 10.0 + (roi_pct / 300.0) * 90.0


def normalize_profit_score(
    result: Optional[ProfitResult], sub_weights: EconomicsSubWeights
) -> float:
    """
    Normalize profit and economics results to a 0-100 scale using sub-weights.

    Applies a safety cap if the transaction is unprofitable.

    Args:
        result: ProfitResult instance from ProfitCalculator
        sub_weights: EconomicsSubWeights configuration

    Returns:
        Normalized economics score (0.0 to 100.0)
    """
    if not result:
        return 0.0

    margin_score = normalize_margin(result.profit_margin)
    profit_score = normalize_absolute_profit(result.net_profit_per_item)
    roi_score = normalize_roi(result.roi)

    weighted_score = (
        margin_score * sub_weights.profit_margin
        + profit_score * sub_weights.absolute_profit
        + roi_score * sub_weights.roi
    )

    # Safety override: cap at 15.0 if unprofitable (losses/break-even)
    if not result.is_profitable:
        weighted_score = min(weighted_score, 15.0)

    return max(0.0, min(100.0, weighted_score))


def normalize_match_score(
    result: Optional[ProductMatchResult], sub_weights: MatchSubWeights
) -> float:
    """
    Normalize product matching quality results to a 0-100 scale.

    Dynamically redistributes weights if the optional supplier_rating sub-weight is unused,
    ensuring mathematical consistency with the existing matcher's capabilities.

    Args:
        result: ProductMatchResult instance from ProductMatcher
        sub_weights: MatchSubWeights configuration

    Returns:
        Normalized match quality score (0.0 to 100.0)
    """
    if not result:
        return 0.0

    scaled_match = float(result.match_score) * 100.0
    scaled_attr = (
        float(result.attribute_similarity) * 100.0
        if getattr(result, "attribute_similarity", None) is not None
        else 0.0
    )

    # Dynamically redistribute supplier_rating sub-weight if absent in match result
    # Pro-rates supplier_rating over the remaining active components
    if sub_weights.supplier_rating > 0.0:
        active_sum = sub_weights.match_confidence + sub_weights.attribute_similarity
        if active_sum > 0.0:
            weight_match = sub_weights.match_confidence / active_sum
            weight_attr = sub_weights.attribute_similarity / active_sum
        else:
            weight_match = 0.60
            weight_attr = 0.40
    else:
        weight_match = sub_weights.match_confidence
        weight_attr = sub_weights.attribute_similarity

    weighted_score = (scaled_match * weight_match) + (scaled_attr * weight_attr)
    return max(0.0, min(100.0, weighted_score))


def calculate_policy_penalty(assessment: Optional[PolicyAssessment]) -> float:
    """
    Calculate policy risk penalty multiplier.

    LOW -> 1.0 (No penalty)
    REVIEW_REQUIRED -> 0.85 (Minor penalty)
    MEDIUM -> 0.65 (Moderate penalty)
    HIGH -> 0.30 (Severe penalty)
    None -> 1.0 (No penalty, missing assessment)

    Args:
        assessment: Optional PolicyAssessment instance

    Returns:
        Penalty multiplier (0.0 to 1.0)
    """
    if not assessment:
        return 1.0

    risk_level = assessment.overall_risk

    penalty_map = {
        PolicyRiskLevel.LOW: 1.0,
        PolicyRiskLevel.REVIEW_REQUIRED: 0.85,
        PolicyRiskLevel.MEDIUM: 0.65,
        PolicyRiskLevel.HIGH: 0.30,
    }

    return penalty_map.get(risk_level, 1.0)