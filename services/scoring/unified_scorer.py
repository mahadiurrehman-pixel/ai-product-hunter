"""
Unified Opportunity Scorer Engine.

Combines 5 major signal streams into a single explainable 0-100 opportunity score:
1. Market / Demand signals (30%)
2. Competition signals (20%)
3. Profit / Economics signals (30%)
4. Supplier Match Quality signals (15%)
5. Confidence Bonus signals (5%)

Applies Policy Risk as a post-weighting multiplier and classifies the result
into actionable recommendation tiers (STRONG_BUY, BUY, HOLD, AVOID, HIGH_RISK).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from services.policy.models import PolicyAssessment, PolicyRiskLevel
from services.profit.models import ProfitResult
from services.scoring.competition_signals import CompetitionSignals
from services.scoring.market_signals import MarketSignals
from services.scoring.normalizers import (
    calculate_policy_penalty,
    normalize_competition_score,
    normalize_margin,
    normalize_market_score,
    normalize_match_score,
    normalize_profit_score,
)
from services.scoring.recommendation import (
    Recommendation,
    classify_recommendation,
)
from services.scoring.weights import (
    ScoringConfig,
    load_scoring_config,
)
from utils.logger import get_logger

if TYPE_CHECKING:
    from services.matching.matcher import ProductMatchResult

logger = get_logger(__name__)


@dataclass
class UnifiedOpportunityScore:
    """Complete, transparent opportunity evaluation output."""

    # Final score & classification
    final_score: float  # 0.0 to 100.0 (after policy penalty multiplier)
    recommendation: Recommendation
    confidence: str  # "high", "medium", "low"

    # Normalized component scores (0.0 to 100.0 each)
    market_score: float
    competition_score: float
    economics_score: float
    match_quality_score: float
    confidence_bonus: float

    # Raw weighted sum before policy penalty
    raw_weighted_score: float

    # Policy details
    policy_penalty: float  # 0.0 to 1.0 multiplier
    policy_risk_level: str

    # Weights used (for auditing)
    weights_used: Dict[str, float]

    # Explainability & transparency
    reasoning: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)

    # Component details for persistence
    market_details: Dict[str, Any] = field(default_factory=dict)
    competition_details: Dict[str, Any] = field(default_factory=dict)
    economics_details: Dict[str, Any] = field(default_factory=dict)
    match_details: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    scored_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert score model to dictionary."""
        return {
            "final_score": round(self.final_score, 2),
            "recommendation": self.recommendation.value,
            "recommendation_label": self.recommendation.label,
            "confidence": self.confidence,
            "raw_weighted_score": round(self.raw_weighted_score, 2),
            "component_scores": {
                "market": round(self.market_score, 2),
                "competition": round(self.competition_score, 2),
                "economics": round(self.economics_score, 2),
                "match_quality": round(self.match_quality_score, 2),
                "confidence_bonus": round(self.confidence_bonus, 2),
            },
            "policy": {
                "penalty_multiplier": self.policy_penalty,
                "risk_level": self.policy_risk_level,
            },
            "weights_used": self.weights_used,
            "reasoning": self.reasoning,
            "warnings": self.warnings,
            "assumptions": self.assumptions,
            "scored_at": self.scored_at,
        }


class UnifiedOpportunityScorer:
    """
    Unified 5-Dimension Opportunity Scoring Engine.

    Combines signals, applies configuration weights, enforces safety overrides,
    and returns transparent, human-readable explanations.
    """

    def __init__(self, config: Optional[ScoringConfig] = None):
        self._config = config or load_scoring_config()

    @property
    def config(self) -> ScoringConfig:
        return self._config

    def score(
        self,
        market_signals: Optional[MarketSignals],
        competition_signals: Optional[CompetitionSignals],
        profit_result: Optional[ProfitResult],
        match_result: Optional[ProductMatchResult],
        policy_assessment: Optional[PolicyAssessment] = None,
    ) -> UnifiedOpportunityScore:
        """
        Calculate unified opportunity score combining all 5 signals.

        Args:
            market_signals: MarketSignals from MarketSignalsAnalyzer
            competition_signals: CompetitionSignals from CompetitionSignalsAnalyzer
            profit_result: ProfitResult from ProfitCalculator
            match_result: ProductMatchResult from ProductMatcher
            policy_assessment: Optional PolicyAssessment from PolicyChecker

        Returns:
            UnifiedOpportunityScore model
        """
        w = self._config.weights
        econ_sub = self._config.economics_sub
        match_sub = self._config.match_sub
        thresholds = self._config.thresholds

        warnings: List[str] = []
        assumptions: List[str] = []

        # 1. Normalize component scores (0.0 to 100.0)
        market_score = normalize_market_score(market_signals)
        competition_score = normalize_competition_score(competition_signals)
        economics_score = normalize_profit_score(profit_result, econ_sub)
        match_quality_score = normalize_match_score(match_result, match_sub)

        # 2. Compute confidence bonus (0.0 to 100.0)
        confidence_bonus, overall_confidence = self._calculate_confidence(
            market_signals, profit_result, match_result, policy_assessment, warnings
        )

        # 3. Calculate weighted sum (Raw Score)
        raw_weighted_score = (
            (market_score * w.market_signals)
            + (competition_score * w.competition_signals)
            + (economics_score * w.economics_signals)
            + (match_quality_score * w.supplier_match_signals)
            + (confidence_bonus * w.confidence_bonus)
        )
        raw_weighted_score = max(0.0, min(100.0, raw_weighted_score))

        # 4. Calculate Policy Penalty
        policy_penalty = calculate_policy_penalty(policy_assessment)
        policy_risk_str = (
            policy_assessment.overall_risk.value
            if policy_assessment
            else "not_checked"
        )
        if not policy_assessment:
            assumptions.append("Policy check not provided — no policy penalty applied")

        # 5. Compute Final Score
        final_score = raw_weighted_score * policy_penalty
        final_score = max(0.0, min(100.0, final_score))

        # 6. Recommendation Classification with Safety Overrides
        is_profitable = profit_result.is_profitable if profit_result else False
        recommendation = classify_recommendation(
            final_score=final_score,
            is_profitable=is_profitable,
            policy_assessment=policy_assessment,
            thresholds=thresholds,
        )

        # 7. Inherit warnings and assumptions from child components
        if profit_result:
            warnings.extend(profit_result.warnings)
            assumptions.extend(profit_result.assumptions)

        # 8. Build Explanation / Reasoning
        reasoning = self._build_reasoning(
            market_score,
            competition_score,
            economics_score,
            match_quality_score,
            overall_confidence,
            policy_assessment,
            profit_result,
            match_result,
        )

        # 9. Extract component details for database persistence
        market_details = self._extract_market_details(market_signals)
        competition_details = self._extract_competition_details(competition_signals)
        economics_details = self._extract_economics_details(profit_result)
        match_details = self._extract_match_details(match_result)

        return UnifiedOpportunityScore(
            final_score=final_score,
            recommendation=recommendation,
            confidence=overall_confidence,
            market_score=market_score,
            competition_score=competition_score,
            economics_score=economics_score,
            match_quality_score=match_quality_score,
            confidence_bonus=confidence_bonus,
            raw_weighted_score=raw_weighted_score,
            policy_penalty=policy_penalty,
            policy_risk_level=policy_risk_str,
            weights_used=w.to_dict(),
            reasoning=reasoning,
            warnings=list(dict.fromkeys(warnings)),  # Deduplicate
            assumptions=list(dict.fromkeys(assumptions)),
            market_details=market_details,
            competition_details=competition_details,
            economics_details=economics_details,
            match_details=match_details,
        )

    def _calculate_confidence(
        self,
        market: Optional[MarketSignals],
        profit: Optional[ProfitResult],
        match: Optional[ProductMatchResult],
        policy: Optional[PolicyAssessment],
        warnings: List[str],
    ) -> tuple[float, str]:
        """Compute 0-100 confidence bonus and 'high'/'medium'/'low' label."""
        match_conf = float(match.confidence) if match and getattr(match, "confidence", None) is not None else 0.5
        market_conf = float(market.confidence) if market and getattr(market, "confidence", None) is not None else 0.5

        profit_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
        profit_conf_str = profit.confidence.lower() if profit and getattr(profit, "confidence", None) else "medium"
        profit_conf = profit_map.get(profit_conf_str, 0.5)

        avg_conf = (match_conf + market_conf + profit_conf) / 3.0

        # Policy risk degrades confidence
        if policy:
            if policy.overall_risk == PolicyRiskLevel.HIGH:
                avg_conf *= 0.5
                warnings.append("High policy risk reduced score confidence")
            elif policy.overall_risk == PolicyRiskLevel.MEDIUM:
                avg_conf *= 0.75

        confidence_bonus = max(0.0, min(100.0, avg_conf * 100.0))

        # Classify label
        t = self._config.thresholds
        if avg_conf >= t.high_confidence:
            label = "high"
        elif avg_conf >= t.medium_confidence:
            label = "medium"
        else:
            label = "low"

        return confidence_bonus, label

    def _build_reasoning(
        self,
        market_score: float,
        competition_score: float,
        economics_score: float,
        match_score: float,
        confidence_label: str,
        policy: Optional[PolicyAssessment],
        profit: Optional[ProfitResult],
        match: Optional[ProductMatchResult],
    ) -> List[str]:
        """Build transparent, human-readable scoring explanation."""
        reasoning = []

        # Market
        if market_score >= 70:
            reasoning.append(f"✅ Strong market demand ({market_score:.0f}/100)")
        elif market_score >= 50:
            reasoning.append(f"🟡 Moderate market demand ({market_score:.0f}/100)")
        else:
            reasoning.append(f"⚠️ Weak market demand ({market_score:.0f}/100)")

        # Competition
        if competition_score >= 70:
            reasoning.append(f"🏆 Favorable low competition ({competition_score:.0f}/100)")
        elif competition_score >= 50:
            reasoning.append(f"🟡 Moderate competition ({competition_score:.0f}/100)")
        else:
            reasoning.append(f"⚠️ Highly competitive market ({competition_score:.0f}/100)")

        # Economics
        if profit:
            reasoning.append(
                f"💰 Economics score: {economics_score:.0f}/100 "
                f"(Margin: {profit.profit_margin:.1f}%, ROI: {profit.roi:.1f}%, Net: {profit.currency} {profit.net_profit_per_item:.2f})"
            )
        else:
            reasoning.append("⚠️ Economics data missing")

        # Match Quality
        if match:
            reasoning.append(
                f"🔗 Supplier Match: {match_score:.0f}/100 (Type: {match.match_type}, Confidence: {match.confidence:.0%})"
            )

        # Policy
        if policy and policy.overall_risk != PolicyRiskLevel.LOW:
            reasoning.append(
                f"⚠️ Policy Warning: {policy.overall_risk.badge} — score penalized"
            )

        reasoning.append(f"🔍 Confidence level: {confidence_label.upper()}")

        return reasoning

    def _extract_market_details(self, market: Optional[MarketSignals]) -> Dict[str, Any]:
        if not market:
            return {}
        return {
            "overall_market_score": market.overall_market_score,
            "listings_analyzed": market.listings_analyzed,
            "price_stability_score": market.price_stability_score,
            "price_cv": market.price_coefficient_of_variation,
            "estimated_sold": market.total_estimated_sold,
        }

    def _extract_competition_details(self, comp: Optional[CompetitionSignals]) -> Dict[str, Any]:
        if not comp:
            return {}
        return {
            "overall_competition_score": comp.overall_competition_score,
            "competition_level": comp.competition_level,
        }

    def _extract_economics_details(self, profit: Optional[ProfitResult]) -> Dict[str, Any]:
        if not profit:
            return {}
        return {
            "net_profit": float(profit.net_profit_per_item),
            "profit_margin": profit.profit_margin,
            "roi": profit.roi,
            "is_profitable": profit.is_profitable,
            "total_fees": float(profit.fees.total_fees),
        }

    def _extract_match_details(self, match: Optional[ProductMatchResult]) -> Dict[str, Any]:
        if not match:
            return {}
        return {
            "match_score": float(match.match_score),
            "match_type": match.match_type,
            "confidence": float(match.confidence),
            "attribute_similarity": float(match.attribute_similarity) if match.attribute_similarity else None,
        }