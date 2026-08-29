"""
Competition indicators from eBay listing data.

Analyzes observable competitive characteristics:
- Free shipping prevalence
- Fixed price vs auction prevalence

These are INDICATORS, not definitive proof of competition level.
Market dynamics are complex and these signals provide partial information.

Calibration rationale:
- Free shipping at 70%+ is genuinely high competition
- Free shipping below 30% is genuinely low competition
- Fixed price dominance (80%+) indicates retail market
- Thresholds chosen so normal retail does not automatically
  score as "Very High Competition"
"""
from dataclasses import dataclass
from typing import List

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CompetitionSignals:
    """
    Competition indicators from analyzed eBay listings.

    Higher scores indicate MORE competitive characteristics.

    IMPORTANT: These are indicators based on observable marketplace
    characteristics, not proven measures of actual competition level.
    """

    free_shipping_score: float
    free_shipping_percentage: float
    shipping_interpretation: str

    market_type_score: float
    fixed_price_percentage: float
    market_type_interpretation: str

    overall_competition_score: float
    competition_level: str


class CompetitionSignalsAnalyzer:
    """
    Analyzes competition indicators from eBay listings.

    Calibration:
    - Free shipping threshold for max score raised to 70%
      (was 50% — too aggressive for normal retail)
    - "Very High Competition" threshold raised to 85
      (was 75 — fired for all normal retail)
    - Competition level labels clarified as "indicators"
    """

    def analyze(self, listings: List[dict]) -> CompetitionSignals:
        """
        Analyze competition indicators from eBay listings.

        Args:
            listings: List of parsed eBay listings

        Returns:
            CompetitionSignals with indicator analysis
        """
        if not listings:
            return self._empty_signals()

        (
            shipping_score,
            shipping_pct,
            shipping_interp,
        ) = self._analyze_shipping(listings)

        (
            market_score,
            fixed_pct,
            market_interp,
        ) = self._analyze_market_type(listings)

        # Overall competition indicator
        # Weight: 60% shipping, 40% market type (heuristic MVP choice)
        overall_score = shipping_score * 0.6 + market_score * 0.4

        # Recalibrated thresholds:
        # 85+ = Very High (was 75 — too aggressive)
        # 65+ = High
        # 40+ = Moderate
        # <40 = Low
        if overall_score >= 90:
            level = "🔴 Very High Competition Indicators"
        elif overall_score >= 65:
            level = "🟠 High Competition Indicators"
        elif overall_score >= 40:
            level = "🟡 Moderate Competition Indicators"
        else:
            level = "🟢 Low Competition Indicators"
        return CompetitionSignals(
            free_shipping_score=shipping_score,
            free_shipping_percentage=shipping_pct,
            shipping_interpretation=shipping_interp,
            market_type_score=market_score,
            fixed_price_percentage=fixed_pct,
            market_type_interpretation=market_interp,
            overall_competition_score=round(overall_score, 1),
            competition_level=level,
        )

    def _analyze_shipping(
        self, listings: List[dict]
    ) -> tuple[float, float, str]:
        """
        Analyze free shipping prevalence.

        Recalibrated bands:
        - <10%:  Very low   → score 0-40
        - 10-30%: Low       → score 40-60
        - 30-50%: Moderate  → score 60-75
        - 50-70%: High      → score 75-90
        - 70%+:  Very high  → score 90-100

        Rationale: 50% free shipping is common in normal retail.
        Treating it as maximum competition was too aggressive.
        70%+ is a genuinely high signal of competitive free shipping.

        Args:
            listings: Parsed eBay listings

        Returns:
            Tuple of (score, percentage, interpretation)
        """
        total = len(listings)
        free_shipping_count = 0

        for listing in listings:
            shipping_options = listing.get("shipping_options", [])
            if shipping_options:
                for option in shipping_options:
                    if isinstance(option, dict):
                        if option.get("shippingCostType") == "FREE":
                            free_shipping_count += 1
                            break

        percentage = (
            (free_shipping_count / total * 100) if total > 0 else 0
        )

        # Recalibrated scoring bands
        if percentage >= 70:
            score = 90.0 + (percentage - 70) / 3.0  # 90 → 100
            score = min(score, 100.0)
            interpretation = (
                f"Very High Free Shipping ({percentage:.0f}%) — "
                "strong competitive pressure on shipping"
            )
        elif percentage >= 50:
            score = 75.0 + (percentage - 50) * 0.75  # 75 → 90
            interpretation = (
                f"High Free Shipping ({percentage:.0f}%) — "
                "competitive but common in retail"
            )
        elif percentage >= 30:
            score = 60.0 + (percentage - 30) * 0.75  # 60 → 75
            interpretation = (
                f"Moderate Free Shipping ({percentage:.0f}%)"
            )
        elif percentage >= 10:
            score = 40.0 + (percentage - 10) * 1.0  # 40 → 60
            interpretation = (
                f"Low Free Shipping ({percentage:.0f}%)"
            )
        else:
            score = percentage * 4.0  # 0 → 40
            interpretation = (
                f"Very Low Free Shipping ({percentage:.0f}%)"
            )

        return round(score, 1), round(percentage, 1), interpretation

    def _analyze_market_type(
        self, listings: List[dict]
    ) -> tuple[float, float, str]:
        """
        Analyze fixed price vs auction prevalence.

        Fixed price dominance = retail/commodity market.
        Auction dominance = collectibles/price-discovery market.

        Bands (unchanged — these were reasonable):
        - 80%+ fixed: Retail Market (score 100)
        - 50-80%: Mixed (score 70-100)
        - <50%: Auction-Heavy (score 0-44)

        Args:
            listings: Parsed eBay listings

        Returns:
            Tuple of (score, percentage, interpretation)
        """
        total = len(listings)
        fixed_price_count = 0

        for listing in listings:
            buying_options = listing.get("buying_options", [])
            if buying_options and "FIXED_PRICE" in buying_options:
                fixed_price_count += 1

        percentage = (fixed_price_count / total * 100) if total > 0 else 0

        if percentage >= 80:
            score = 100.0
            interpretation = "Retail Market (Fixed Price Dominant)"
        elif percentage >= 50:
            score = 70.0 + (percentage - 50) * 1.0
            interpretation = "Mixed Market Type"
        else:
            score = percentage * 0.875
            interpretation = "Auction-Heavy Market"

        return round(score, 1), round(percentage, 1), interpretation

    def _empty_signals(self) -> CompetitionSignals:
        """Return empty signals for no data case."""
        return CompetitionSignals(
            free_shipping_score=0.0,
            free_shipping_percentage=0.0,
            shipping_interpretation="No data",
            market_type_score=0.0,
            fixed_price_percentage=0.0,
            market_type_interpretation="No data",
            overall_competition_score=0.0,
            competition_level="Unknown",
        )
