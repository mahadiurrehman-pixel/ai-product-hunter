"""
Product ranking service.

Ranks eBay listings by observable demand and market signals,
reusing existing Phase 3 analysis. Provides per-listing ranking
without introducing new API calls or unsupported sales claims.

Design rules:
- Reuses MarketSignalsAnalyzer for aggregate context (no duplication)
- Ranks per-listing using signals already returned by eBay search
- Never sorts by raw price
- Never compares prices across currencies
- Never invents sales figures
- Uses honest demand labels tied to evidence quality
- Deterministic output (same input → same order)
"""
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from services.scoring.market_signals import (
    MarketSignalsAnalyzer,
    MarketSignals,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class DemandLabel(str, Enum):
    """
    Honest demand classification tied to evidence quality.

    Never claims verified sales when only estimated/market signals exist.
    """

    # Reliable per-listing sold evidence
    TOP_SELLING = "🔥 Top Selling"
    HIGH_DEMAND_ESTIMATED = "📈 High Demand — Estimated"
    SOME_DEMAND_ESTIMATED = "📊 Some Demand — Estimated"

    # No sold data — inferring from market signals only
    HIGH_MARKET_INTEREST = "📊 High Market Interest"
    MODERATE_INTEREST = "🟡 Moderate Interest"

    # Insufficient data
    LIMITED_DATA = "ℹ️ Demand Data Limited"

    UNKNOWN = "❓ Unknown"


@dataclass
class RankedProduct:
    """
    A single ranked search result.

    Preserves all original listing information plus adds ranking metadata.
    Never overwrites or removes fields from the original listing dict.
    """

    # Rank (1-indexed, 1 = best)
    rank: int

    # Original listing data — preserved verbatim
    item_id: str
    title: str
    price_value: Decimal
    price_currency: str
    marketplace: str
    image_url: Optional[str]
    item_web_url: Optional[str]
    condition: Optional[str]

    # Seller info (preserved)
    seller_username: Optional[str]
    seller_feedback_percentage: Optional[float]

    # Ranking metadata
    ranking_score: float  # 0-100, higher = better ranked
    demand_label: DemandLabel
    demand_reason: str  # human-readable explanation of demand classification
    confidence: str  # "high" | "medium" | "low"

    # Signal breakdown (for transparency)
    sold_signal_available: bool
    estimated_sold_quantity: Optional[int]
    market_score: float  # aggregate market score from MarketSignals
    market_confidence_label: str  # from MarketSignals

    # Original raw listing (preserved for downstream consumers)
    original_listing: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize for display/UI."""
        return {
            "rank": self.rank,
            "item_id": self.item_id,
            "title": self.title,
            "price": {
                "value": float(self.price_value),
                "currency": self.price_currency,
            },
            "marketplace": self.marketplace,
            "image_url": self.image_url,
            "item_web_url": self.item_web_url,
            "condition": self.condition,
            "seller": {
                "username": self.seller_username,
                "feedback_percentage": self.seller_feedback_percentage,
            },
            "demand": {
                "label": self.demand_label.value,
                "reason": self.demand_reason,
                "confidence": self.confidence,
                "sold_data_available": self.sold_signal_available,
                "estimated_sold_quantity": self.estimated_sold_quantity,
            },
            "ranking_score": round(self.ranking_score, 1),
            "market_score": round(self.market_score, 1),
            "market_confidence_label": self.market_confidence_label,
        }


class ProductRankingService:
    """
    Ranks eBay search results by observable demand signals.

    Reuses MarketSignalsAnalyzer (Phase 3) for aggregate context.
    Ranks individual listings using per-listing signals from the
    same eBay API response — zero additional API calls.

    Ranking formula (heuristic MVP weights):

    When sold_signal available for a listing:
        score = sold_signal      * 0.40
              + seller_quality   * 0.20
              + market_context   * 0.25
              + competitiveness  * 0.15

    When sold_signal unavailable:
        score = seller_quality   * 0.35
              + market_context   * 0.45
              + competitiveness  * 0.20

    All component scores are normalized to 0-100 before weighting.

    Deterministic sort:
    1. Ranking score (descending)
    2. Estimated sold quantity (descending, when present)
    3. Seller feedback score (descending, when present)
    4. Item ID (ascending, guarantees stable order)
    """

    # Demand thresholds tied to eBay estimated_sold_quantity
    # (per-listing estimate, not marketplace-wide)
    SOLD_THRESHOLD_TOP = 50
    SOLD_THRESHOLD_HIGH = 10

    # Market score thresholds for demand labels when no sold data
    MARKET_SCORE_HIGH_INTEREST = 65
    MARKET_SCORE_MODERATE = 45

    def __init__(
        self,
        market_analyzer: Optional[MarketSignalsAnalyzer] = None,
    ):
        """
        Initialize ranking service.

        Args:
            market_analyzer: Optional analyzer instance for testing.
                             Defaults to new MarketSignalsAnalyzer.
        """
        self.market_analyzer = market_analyzer or MarketSignalsAnalyzer()

    def rank(
        self,
        listings: List[dict],
        total_available: Optional[int] = None,
    ) -> List[RankedProduct]:
        """
        Rank eBay search results by demand and market signals.

        Args:
            listings: Parsed eBay listing dicts from EbayClient.search_items()
            total_available: Total eBay results for the query
                             (from response["total"]) — improves market context

        Returns:
            List of RankedProduct, sorted best-first. Empty list if no listings.
        """
        if not listings:
            logger.info("No listings provided to ranker")
            return []

        # Run aggregate market analysis ONCE (reuses Phase 3)
        market_signals = self.market_analyzer.analyze(
            listings, total_available=total_available
        )

        logger.info(
            f"Ranking {len(listings)} listings — "
            f"market_score={market_signals.overall_market_score}, "
            f"confidence={market_signals.confidence_label}"
        )

        # Score every listing
        scored = []
        for listing in listings:
            try:
                ranking_score, breakdown = self._score_listing(
                    listing, market_signals
                )
                demand_label, demand_reason, confidence = (
                    self._classify_demand(listing, market_signals)
                )
                scored.append(
                    {
                        "listing": listing,
                        "ranking_score": ranking_score,
                        "breakdown": breakdown,
                        "demand_label": demand_label,
                        "demand_reason": demand_reason,
                        "confidence": confidence,
                    }
                )
            except Exception as e:
                logger.warning(
                    f"Failed to rank listing "
                    f"{listing.get('item_id')}: {e}"
                )
                continue

        # Deterministic sort
        scored.sort(
            key=lambda x: (
                -x["ranking_score"],
                -(x["listing"].get("estimated_sold_quantity") or 0),
                -(x["listing"].get("seller_feedback_score") or 0),
                x["listing"].get("item_id") or "",
            )
        )

        # Build RankedProduct results
        ranked = []
        for idx, entry in enumerate(scored, start=1):
            listing = entry["listing"]
            ranked.append(
                RankedProduct(
                    rank=idx,
                    item_id=listing.get("item_id", ""),
                    title=listing.get("title", ""),
                    price_value=self._safe_decimal(
                        listing.get("price_value")
                    ),
                    price_currency=listing.get("price_currency", "USD"),
                    marketplace=listing.get("marketplace", "EBAY_US"),
                    image_url=listing.get("image_url"),
                    item_web_url=listing.get("item_web_url"),
                    condition=listing.get("condition"),
                    seller_username=listing.get("seller_username"),
                    seller_feedback_percentage=listing.get(
                        "seller_feedback_percentage"
                    ),
                    ranking_score=entry["ranking_score"],
                    demand_label=entry["demand_label"],
                    demand_reason=entry["demand_reason"],
                    confidence=entry["confidence"],
                    sold_signal_available=(
                        listing.get("estimated_sold_quantity") is not None
                    ),
                    estimated_sold_quantity=listing.get(
                        "estimated_sold_quantity"
                    ),
                    market_score=market_signals.overall_market_score,
                    market_confidence_label=(
                        market_signals.confidence_label
                    ),
                    original_listing=listing,
                )
            )

        return ranked

    def _score_listing(
        self,
        listing: dict,
        market_signals: MarketSignals,
    ) -> tuple[float, dict]:
        """
        Score a single listing.

        Returns:
            Tuple of (ranking_score, component_breakdown_dict)
        """
        sold_signal = self._score_sold_signal(listing)
        seller_quality = self._score_seller_quality(listing)
        market_context = market_signals.overall_market_score
        competitiveness = self._score_competitiveness(listing)

        breakdown = {
            "sold_signal": sold_signal,
            "seller_quality": seller_quality,
            "market_context": market_context,
            "competitiveness": competitiveness,
        }

        # Dynamic weighting
        if sold_signal is not None:
            score = (
                sold_signal * 0.40
                + seller_quality * 0.20
                + market_context * 0.25
                + competitiveness * 0.15
            )
        else:
            score = (
                seller_quality * 0.35
                + market_context * 0.45
                + competitiveness * 0.20
            )

        return round(score, 2), breakdown

    def _score_sold_signal(self, listing: dict) -> Optional[float]:
        """
        Score based on eBay estimated_sold_quantity for this listing.

        Returns:
            0-100 score, or None if no sold data available
        """
        sold = listing.get("estimated_sold_quantity")
        if sold is None or sold < 0:
            return None

        if sold >= 100:
            return 100.0
        elif sold >= 50:
            return 85.0
        elif sold >= 20:
            return 70.0
        elif sold >= 10:
            return 55.0
        elif sold >= 5:
            return 40.0
        else:
            return 25.0

    def _score_seller_quality(self, listing: dict) -> float:
        """
        Score based on seller feedback percentage.

        Returns:
            0-100 score. 50 if no data available.
        """
        feedback = listing.get("seller_feedback_percentage")
        if feedback is None:
            return 50.0

        try:
            feedback = float(feedback)
        except (ValueError, TypeError):
            return 50.0

        if feedback >= 99:
            return 100.0
        elif feedback >= 97:
            return 85.0
        elif feedback >= 95:
            return 70.0
        elif feedback >= 90:
            return 55.0
        elif feedback >= 85:
            return 40.0
        else:
            return 25.0

    def _score_competitiveness(self, listing: dict) -> float:
        """
        Score seller competitiveness signals.

        Combines:
        - Free shipping offered (+ points)
        - Fixed price offering (+ points; auction implies uncertainty)

        Returns:
            0-100 score
        """
        score = 50.0  # neutral baseline

        # Free shipping bonus
        shipping_options = listing.get("shipping_options") or []
        if isinstance(shipping_options, list):
            for opt in shipping_options:
                if isinstance(opt, dict) and opt.get("shippingCostType") == "FREE":
                    score += 25.0
                    break

        # Fixed price bonus (retail signal)
        buying_options = listing.get("buying_options") or []
        if isinstance(buying_options, list) and "FIXED_PRICE" in buying_options:
            score += 25.0

        return min(100.0, score)

    def _classify_demand(
        self,
        listing: dict,
        market_signals: MarketSignals,
    ) -> tuple[DemandLabel, str, str]:
        """
        Classify demand for a listing based on available evidence.

        Returns:
            Tuple of (DemandLabel, human_reason, confidence)
        """
        sold = listing.get("estimated_sold_quantity")

        # Case 1: We have per-listing sold data from eBay
        if sold is not None and sold >= 0:
            if sold >= self.SOLD_THRESHOLD_TOP:
                return (
                    DemandLabel.TOP_SELLING,
                    f"eBay estimates {sold}+ sold for this listing",
                    "high",
                )
            elif sold >= self.SOLD_THRESHOLD_HIGH:
                return (
                    DemandLabel.HIGH_DEMAND_ESTIMATED,
                    f"eBay estimates ~{sold} sold for this listing",
                    "medium",
                )
            else:
                return (
                    DemandLabel.SOME_DEMAND_ESTIMATED,
                    f"eBay estimates ~{sold} sold for this listing",
                    "medium",
                )

        # Case 2: No sold data — use aggregate market signals
        market_score = market_signals.overall_market_score
        market_confidence = market_signals.confidence

        if market_confidence < 0.30:
            return (
                DemandLabel.LIMITED_DATA,
                "Insufficient data to assess demand reliably",
                "low",
            )

        if market_score >= self.MARKET_SCORE_HIGH_INTEREST:
            return (
                DemandLabel.HIGH_MARKET_INTEREST,
                (
                    f"Strong overall market signals "
                    f"(score {market_score:.0f}/100) — "
                    "individual listing sales not disclosed by eBay"
                ),
                "medium" if market_confidence >= 0.60 else "low",
            )
        elif market_score >= self.MARKET_SCORE_MODERATE:
            return (
                DemandLabel.MODERATE_INTEREST,
                (
                    f"Moderate market signals "
                    f"(score {market_score:.0f}/100) — "
                    "individual listing sales not disclosed by eBay"
                ),
                "medium" if market_confidence >= 0.60 else "low",
            )
        else:
            return (
                DemandLabel.LIMITED_DATA,
                (
                    f"Weak market signals "
                    f"(score {market_score:.0f}/100) — "
                    "insufficient demand evidence"
                ),
                "low",
            )

    def _safe_decimal(self, value) -> Decimal:
        """Safely convert value to Decimal for price handling."""
        if value is None:
            return Decimal("0")
        try:
            return Decimal(str(value))
        except Exception:
            return Decimal("0")