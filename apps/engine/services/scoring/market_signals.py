"""
Market signals analysis from eBay listing data.

Analyzes observable market activity using ONLY verified available data
from eBay Browse API. Does NOT fabricate sales data or make unsupported
claims about total market size.

Important:
- Analyzes retrieved/analyzed listings, not all eBay listings
- Uses optional estimated_sold_quantity only when actually available
- Uses total_available (from eBay search response) for listing activity
  when provided, otherwise falls back to len(listings) with lower confidence
- Transparent about data limitations
"""
from dataclasses import dataclass
from typing import List, Optional
import statistics

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MarketSignals:
    """
    Market activity signals from analyzed eBay listings.

    Based on observable data only. Does NOT claim to represent
    complete marketplace or guaranteed demand.
    """

    # Listing activity
    listing_activity_score: float  # 0-100
    listings_analyzed: int         # Number we actually retrieved/analyzed
    total_available: Optional[int] # Total matching eBay results (from API)
    listing_activity_interpretation: str

    # Price analysis
    price_stability_score: float
    mean_price: float
    price_std_dev: float
    price_coefficient_of_variation: float
    price_interpretation: str

    # Seller quality
    seller_quality_score: float
    avg_seller_feedback: Optional[float]
    seller_quality_interpretation: str

    # Estimated sold quantity (OPTIONAL)
    estimated_sold_signal: Optional[float]
    estimated_sold_available: bool
    total_estimated_sold: Optional[int]

    # Overall
    overall_market_score: float
    confidence: float          # 0-1, combines signal availability + sample size
    confidence_label: str      # Human-readable confidence description
    signals_available: List[str]
    signals_missing: List[str]


class MarketSignalsAnalyzer:
    """
    Analyzes market signals from eBay listings.

    Uses only verified available eBay Browse API data.
    Does not fabricate or estimate unavailable data.
    """

    # Sample size tiers for confidence calculation
    # These are defensible MVP thresholds — not statistically rigorous
    SAMPLE_SIZE_TIERS = [
        (0,  0,    0.00, "No data"),
        (1,  4,    0.25, "Very Low (too few listings for reliable signals)"),
        (5,  9,    0.50, "Low (limited sample)"),
        (10, 19,   0.70, "Moderate (reasonable sample)"),
        (20, None, 0.90, "Good (sufficient sample)"),
    ]

    def analyze(
        self,
        listings: List[dict],
        total_available: Optional[int] = None,
    ) -> MarketSignals:
        """
        Analyze market signals from eBay listings.

        Args:
            listings: List of parsed eBay listings from EbayParser
            total_available: Total number of eBay results for the query
                             (from response["total"]). When provided, used
                             for listing activity scoring instead of
                             len(listings). When None, falls back to
                             len(listings) with reduced confidence.

        Returns:
            MarketSignals with scores and transparent analysis
        """
        if not listings:
            logger.warning("No listings provided for market analysis")
            return self._empty_signals()

        # Determine which count to use for listing activity
        # total_available reflects the real market size on eBay
        # len(listings) reflects only what we retrieved
        activity_count = total_available if total_available is not None else len(listings)
        using_total = total_available is not None

        if not using_total:
            logger.warning(
                "total_available not provided to MarketSignalsAnalyzer. "
                "Listing activity will use retrieved count (%d), which may "
                "underestimate actual market size.",
                len(listings),
            )

        # Analyze each component
        listing_score, listing_interp = self._analyze_listing_activity(
            activity_count, using_total=using_total
        )

        (
            price_score,
            price_stats,
            price_interp,
        ) = self._analyze_price_stability(listings)

        (
            seller_score,
            avg_feedback,
            seller_interp,
        ) = self._analyze_seller_quality(listings)

        (
            sold_score,
            sold_available,
            total_sold,
        ) = self._analyze_estimated_sold(listings)

        # Track which signals we have
        signals_available = ["listing_activity", "price_analysis"]
        signals_missing = []

        if avg_feedback is not None:
            signals_available.append("seller_quality")
        else:
            signals_missing.append("seller_quality")

        if sold_available:
            signals_available.append("estimated_sold")
        else:
            signals_missing.append("estimated_sold")

        # Calculate confidence combining sample size + signal availability
        confidence, confidence_label = self._calculate_confidence(
            sample_size=len(listings),
            signals_available=signals_available,
            using_total=using_total,
        )

        # Calculate overall score
        overall_score = self._calculate_overall_score(
            listing_score=listing_score,
            price_score=price_score,
            seller_score=seller_score,
            sold_score=sold_score,
            sold_available=sold_available,
        )

        return MarketSignals(
            listing_activity_score=listing_score,
            listings_analyzed=len(listings),
            total_available=total_available,
            listing_activity_interpretation=listing_interp,
            price_stability_score=price_score,
            mean_price=price_stats["mean"],
            price_std_dev=price_stats["std_dev"],
            price_coefficient_of_variation=price_stats["cv"],
            price_interpretation=price_interp,
            seller_quality_score=seller_score,
            avg_seller_feedback=avg_feedback,
            seller_quality_interpretation=seller_interp,
            estimated_sold_signal=sold_score,
            estimated_sold_available=sold_available,
            total_estimated_sold=total_sold,
            overall_market_score=overall_score,
            confidence=confidence,
            confidence_label=confidence_label,
            signals_available=signals_available,
            signals_missing=signals_missing,
        )

    def _analyze_listing_activity(
        self,
        count: int,
        using_total: bool = True,
    ) -> tuple[float, str]:
        """
        Score based on listing count.

        When using_total=True, count is the real eBay search total —
        a meaningful market size indicator.

        When using_total=False, count is only the retrieved sample —
        interpretation is less reliable and noted explicitly.

        Heuristic scoring bands (MVP):
        - 0-10:      Very limited activity
        - 10-50:     Emerging/niche
        - 50-500:    Established
        - 500-5000:  Competitive
        - 5000+:     Highly saturated

        These are heuristic MVP thresholds, not scientifically validated.

        Args:
            count: Listing count to score
            using_total: Whether count is from eBay total (True)
                         or retrieved sample (False)

        Returns:
            Tuple of (score, interpretation)
        """
        suffix = "" if using_total else " (retrieved sample only)"

        if count == 0:
            return 0.0, f"No listings found{suffix}"
        elif count < 10:
            score = 20.0
            interpretation = f"Very Limited Activity{suffix}"
        elif count < 50:
            score = 20.0 + (count - 10) * 1.0  # 20 → 60
            interpretation = f"Niche/Emerging Market{suffix}"
        elif count < 500:
            score = 60.0 + (count - 50) * (40.0 / 450)  # 60 → 100
            interpretation = f"Established Market{suffix}"
        elif count < 5000:
            score = 100.0 - (count - 500) * (20.0 / 4500)  # 100 → 80
            interpretation = f"Competitive Market{suffix}"
        else:
            score = max(50.0, 80.0 - (count - 5000) * 0.001)
            interpretation = f"Saturated Market{suffix}"

        return round(score, 1), interpretation

    def _calculate_confidence(
        self,
        sample_size: int,
        signals_available: List[str],
        using_total: bool = True,
    ) -> tuple[float, str]:
        """
        Calculate confidence combining sample size and signal availability.

        Confidence here means: "how much should we trust these signals"
        based on how many listings were analyzed and which signals were
        available.

        It does NOT mean: "probability this product will be profitable."

        Sample size tiers (defensible MVP thresholds):
        - 0:      0.00 — no data at all
        - 1-4:    0.25 — too few listings for reliable patterns
        - 5-9:    0.50 — limited sample, treat signals cautiously
        - 10-19:  0.70 — reasonable sample for basic analysis
        - 20+:    0.90 — sufficient for MVP-level analysis

        Final confidence = sample_size_factor * signal_ratio

        If total_available was not provided (using retrieved count for
        listing activity), confidence is further reduced by 10% to
        reflect the additional uncertainty.

        Args:
            sample_size: Number of listings actually analyzed
            signals_available: List of signals that were available
            using_total: Whether listing activity used real eBay total

        Returns:
            Tuple of (confidence_float, confidence_label)
        """
        # Sample size factor
        if sample_size == 0:
            return 0.0, "No data"
        elif sample_size < 5:
            sample_factor = 0.25
            tier_label = "Very Low"
        elif sample_size < 10:
            sample_factor = 0.50
            tier_label = "Low"
        elif sample_size < 20:
            sample_factor = 0.70
            tier_label = "Moderate"
        else:
            sample_factor = 0.90
            tier_label = "Good"

        # Signal availability ratio (max 4 signals)
        max_signals = 4
        signal_ratio = len(signals_available) / max_signals

        # Combined confidence
        confidence = sample_factor * signal_ratio

        # Penalty if we could not use real eBay total
        if not using_total:
            confidence = confidence * 0.90

        confidence = round(min(confidence, 1.0), 2)

        # Build human-readable label
        if sample_size < 5:
            detail = (
                f"Very Low — only {sample_size} listing(s) analyzed. "
                "Too few for reliable signals."
            )
        elif sample_size < 10:
            detail = (
                f"Low — {sample_size} listings analyzed. "
                "Treat signals cautiously."
            )
        elif sample_size < 20:
            detail = (
                f"Moderate — {sample_size} listings analyzed. "
                "Basic analysis only."
            )
        else:
            detail = (
                f"Good — {sample_size} listings analyzed. "
                "Sufficient for MVP-level assessment."
            )

        if not using_total:
            detail += " (listing activity based on retrieved sample, not eBay total)"

        return confidence, detail

    def _analyze_price_stability(
        self, listings: List[dict]
    ) -> tuple[float, dict, str]:
        """
        Analyze price variance to assess market maturity.

        CV bands:
        - CV < 0.15:       Very Stable Pricing
        - CV 0.15 - 0.30:  Variable Pricing
        - CV 0.30 - 0.50:  Unstable Pricing
        - CV > 0.50:       Unstable Pricing

        Args:
            listings: Parsed eBay listings

        Returns:
            Tuple of (score, stats_dict, interpretation)
        """
        prices = []
        for listing in listings:
            try:
                price = float(listing.get("price_value", 0))
                if price > 0:
                    prices.append(price)
            except (ValueError, TypeError):
                continue

        if not prices:
            return (
                50.0,
                {"mean": 0, "std_dev": 0, "cv": 0},
                "Insufficient price data",
            )

        mean_price = statistics.mean(prices)

        if len(prices) < 3:
            return (
                50.0,
                {"mean": round(mean_price, 2), "std_dev": 0, "cv": 0},
                "Insufficient price data",
            )

        std_dev = statistics.stdev(prices)
        cv = (std_dev / mean_price) if mean_price > 0 else 1.0

        if cv < 0.15:
            score = 100.0
            interpretation = "Very Stable Pricing"
        elif cv < 0.30:
            score = 100.0 - (cv - 0.15) * 200
            interpretation = "Variable Pricing"
        elif cv < 0.50:
            score = 70.0 - (cv - 0.30) * 150
            interpretation = "Unstable Pricing"
        else:
            score = max(20.0, 40.0 - (cv - 0.50) * 40)
            interpretation = "Unstable Pricing"

        stats = {
            "mean": round(mean_price, 2),
            "std_dev": round(std_dev, 2),
            "cv": round(cv, 3),
        }

        return round(score, 1), stats, interpretation

    def _analyze_seller_quality(
        self, listings: List[dict]
    ) -> tuple[float, Optional[float], str]:
        """
        Analyze average seller feedback percentage.

        Args:
            listings: Parsed eBay listings

        Returns:
            Tuple of (score, avg_feedback, interpretation)
        """
        feedback_scores = []
        for listing in listings:
            feedback = listing.get("seller_feedback_percentage")
            if feedback is not None:
                try:
                    feedback_scores.append(float(feedback))
                except (ValueError, TypeError):
                    continue

        if not feedback_scores:
            return 50.0, None, "No seller feedback data available"

        avg_feedback = statistics.mean(feedback_scores)

        if avg_feedback >= 95:
            score = 100.0
            interpretation = "High Quality Sellers"
        elif avg_feedback >= 90:
            score = 80.0
            interpretation = "Good Quality Sellers"
        elif avg_feedback >= 85:
            score = 60.0
            interpretation = "Mixed Quality Sellers"
        else:
            score = 40.0
            interpretation = "Lower Quality Sellers"

        return round(score, 1), round(avg_feedback, 1), interpretation

    def _analyze_estimated_sold(
        self, listings: List[dict]
    ) -> tuple[Optional[float], bool, Optional[int]]:
        """
        Analyze estimated sold quantity when available.

        IMPORTANT: This data is OPTIONAL in eBay Browse API.

        Args:
            listings: Parsed eBay listings

        Returns:
            Tuple of (score or None, is_available, total_sold or None)
        """
        sold_quantities = []
        for listing in listings:
            sold = listing.get("estimated_sold_quantity")
            if sold is not None and sold > 0:
                sold_quantities.append(sold)

        if not sold_quantities:
            return None, False, None

        total_sold = sum(sold_quantities)
        avg_sold = statistics.mean(sold_quantities)

        if avg_sold >= 100:
            score = 100.0
        elif avg_sold >= 50:
            score = 75.0
        elif avg_sold >= 10:
            score = 50.0
        else:
            score = 25.0

        return round(score, 1), True, total_sold

    def _calculate_overall_score(
        self,
        listing_score: float,
        price_score: float,
        seller_score: float,
        sold_score: Optional[float],
        sold_available: bool,
    ) -> float:
        """
        Calculate weighted overall market score.

        When all signals available (equal weighting):
        - listing_activity: 25%
        - price_stability: 25%
        - seller_quality: 25%
        - estimated_sold: 25%

        When estimated_sold unavailable:
        - listing_activity: 35%
        - price_stability: 35%
        - seller_quality: 30%

        Args:
            listing_score: Listing activity score
            price_score: Price stability score
            seller_score: Seller quality score
            sold_score: Estimated sold score (or None)
            sold_available: Whether sold data is available

        Returns:
            Overall market score (0-100)
        """
        if sold_available and sold_score is not None:
            score = (
                listing_score * 0.25
                + price_score * 0.25
                + seller_score * 0.25
                + sold_score * 0.25
            )
        else:
            score = (
                listing_score * 0.35
                + price_score * 0.35
                + seller_score * 0.30
            )

        return round(score, 1)

    def _empty_signals(self) -> MarketSignals:
        """Return empty signals for no data case."""
        return MarketSignals(
            listing_activity_score=0.0,
            listings_analyzed=0,
            total_available=None,
            listing_activity_interpretation="No data",
            price_stability_score=0.0,
            mean_price=0.0,
            price_std_dev=0.0,
            price_coefficient_of_variation=0.0,
            price_interpretation="No data",
            seller_quality_score=0.0,
            avg_seller_feedback=None,
            seller_quality_interpretation="No data",
            estimated_sold_signal=None,
            estimated_sold_available=False,
            total_estimated_sold=None,
            overall_market_score=0.0,
            confidence=0.0,
            confidence_label="No data",
            signals_available=[],
            signals_missing=["all"],
        )