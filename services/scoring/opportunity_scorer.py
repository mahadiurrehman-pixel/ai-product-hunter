"""
Legacy Market & Competition Opportunity Scorer.

.. deprecated:: Phase 7
    Use :class:`services.scoring.UnifiedOpportunityScorer` instead.
    This legacy scorer only analyzes market & competition signals without
    evaluating profit economics, match quality, or policy risk.
"""
from dataclasses import dataclass
from typing import List, Optional

from .market_signals import MarketSignalsAnalyzer, MarketSignals
from .competition_signals import (
    CompetitionSignalsAnalyzer,
    CompetitionSignals,
)
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OpportunityScore:
    """
    Complete market opportunity analysis for a product search.

    .. deprecated:: Phase 7
        Use :class:`services.scoring.UnifiedOpportunityScore` for full 5-dimension scoring.
    """

    market_signals: MarketSignals
    competition_signals: CompetitionSignals

    overall_score: float
    confidence: float
    confidence_label: str
    recommendation: str
    reasoning: List[str]

    listings_analyzed: int
    total_available: Optional[int]
    signals_used: List[str]
    limitations: List[str]


class OpportunityScorer:
    """
    Legacy scorer combining market and competition analysis.

    .. deprecated:: Phase 7
        Use :class:`services.scoring.UnifiedOpportunityScorer` instead.
    """

    def __init__(self):
        self.market_analyzer = MarketSignalsAnalyzer()
        self.competition_analyzer = CompetitionSignalsAnalyzer()

    def score(
        self,
        listings: List[dict],
        total_available: Optional[int] = None,
    ) -> OpportunityScore:
        """
        Calculate market opportunity score from eBay listings.

        Args:
            listings: Parsed eBay listings from EbayClient.search_items()
            total_available: Total eBay results for the query
                             (from response["total"]).

        Returns:
            OpportunityScore with complete analysis and limitations
        """
        if not listings:
            return self._empty_score()

        market_signals = self.market_analyzer.analyze(
            listings,
            total_available=total_available,
        )
        competition_signals = self.competition_analyzer.analyze(listings)

        # High competition reduces opportunity (inverted)
        competition_factor = (
            100 - competition_signals.overall_competition_score
        ) / 100

        # Weighted combination: 60% market signals, 40% inverse competition
        overall_score = (
            market_signals.overall_market_score * 0.6
            + competition_factor * 100 * 0.4
        )

        recommendation, reasoning = self._generate_recommendation(
            overall_score,
            market_signals,
            competition_signals,
        )

        signals_used = market_signals.signals_available + [
            "competition_analysis"
        ]

        limitations = [
            f"⚠️ {market_signals.listings_analyzed} listings analyzed"
            + (
                f" out of {total_available} total eBay results"
                if total_available
                else " (total eBay results unknown)"
            ),
            "⚠️ Snapshot at specific time — not historical sales trends",
            "⚠️ eBay data only — excludes other marketplaces",
            "⚠️ Market conditions change rapidly",
            "⚠️ Scoring weights are heuristic MVP rules",
            "⚠️ Does NOT guarantee profitability or success",
        ]

        if not market_signals.estimated_sold_available:
            limitations.append(
                "⚠️ Estimated sold data unavailable for analyzed listings"
            )

        if total_available is None:
            limitations.append(
                "⚠️ Listing activity based on retrieved sample only "
                "(pass total_available for accurate market size scoring)"
            )

        return OpportunityScore(
            market_signals=market_signals,
            competition_signals=competition_signals,
            overall_score=round(overall_score, 1),
            confidence=market_signals.confidence,
            confidence_label=market_signals.confidence_label,
            recommendation=recommendation,
            reasoning=reasoning,
            listings_analyzed=len(listings),
            total_available=total_available,
            signals_used=signals_used,
            limitations=limitations,
        )

    def _generate_recommendation(
        self,
        overall_score: float,
        market: MarketSignals,
        competition: CompetitionSignals,
    ) -> tuple[str, List[str]]:
        """Generate human-readable recommendation and reasoning."""
        reasoning = []

        if market.overall_market_score >= 70:
            reasoning.append(
                f"✅ Strong market signals ({market.overall_market_score:.0f}/100)"
            )
        elif market.overall_market_score >= 50:
            reasoning.append(
                f"🟡 Moderate market signals ({market.overall_market_score:.0f}/100)"
            )
        else:
            reasoning.append(
                f"⚠️ Weak market signals ({market.overall_market_score:.0f}/100)"
            )

        if market.total_available is not None:
            reasoning.append(
                f"📊 {market.total_available} total eBay results "
                f"({market.listings_analyzed} analyzed) — "
                f"{market.listing_activity_interpretation}"
            )
        else:
            reasoning.append(
                f"📊 {market.listings_analyzed} listings analyzed — "
                f"{market.listing_activity_interpretation}"
            )

        if market.price_stability_score >= 70:
            reasoning.append(
                f"💰 Stable pricing "
                f"(CV: {market.price_coefficient_of_variation:.2f})"
            )
        else:
            reasoning.append(
                f"💰 Variable pricing "
                f"(CV: {market.price_coefficient_of_variation:.2f})"
            )

        reasoning.append(f"🏆 {competition.competition_level}")

        if market.estimated_sold_available and market.total_estimated_sold:
            reasoning.append(
                f"📈 ~{market.total_estimated_sold} units sold "
                f"across analyzed listings (eBay estimate only)"
            )

        reasoning.append(
            f"🔍 Analysis confidence: {market.confidence_label}"
        )

        if overall_score >= 70:
            recommendation = (
                "🟢 INVESTIGATE FURTHER — Promising opportunity indicators"
            )
        elif overall_score >= 50:
            recommendation = (
                "🟡 PROCEED WITH CAUTION — Mixed signals"
            )
        else:
            recommendation = (
                "🔴 WEAK OPPORTUNITY — Consider alternatives"
            )

        return recommendation, reasoning

    def _empty_score(self) -> OpportunityScore:
        """Return empty score for no data case."""
        empty_market = self.market_analyzer._empty_signals()
        empty_competition = self.competition_analyzer._empty_signals()

        return OpportunityScore(
            market_signals=empty_market,
            competition_signals=empty_competition,
            overall_score=0.0,
            confidence=0.0,
            confidence_label="No data",
            recommendation="❌ NO DATA — Cannot analyze",
            reasoning=["No listings found"],
            listings_analyzed=0,
            total_available=None,
            signals_used=[],
            limitations=["No data available for analysis"],
        )