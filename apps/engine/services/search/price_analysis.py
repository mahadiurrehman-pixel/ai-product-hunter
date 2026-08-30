"""
Price analysis with IQR outlier detection.

Provides statistically robust price analysis by identifying
and flagging outliers using the Interquartile Range method.

No AI, no APIs — pure statistics on available price data.
"""
import statistics
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PriceStats:
    """Statistical analysis of listing prices."""

    count: int
    median: float
    mean: float
    min_price: float
    max_price: float
    q1: float
    q3: float
    iqr: float
    lower_bound: float  # Q1 - 1.5*IQR
    upper_bound: float  # Q3 + 1.5*IQR
    std_dev: float
    cv: float  # coefficient of variation
    outlier_count: int
    prices_after_outlier_removal: List[float]
    cv_label: str  # "Very Stable" / "Variable" / "Unstable"

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "median": round(self.median, 2),
            "mean": round(self.mean, 2),
            "min": round(self.min_price, 2),
            "max": round(self.max_price, 2),
            "q1": round(self.q1, 2),
            "q3": round(self.q3, 2),
            "iqr": round(self.iqr, 2),
            "lower_bound": round(self.lower_bound, 2),
            "upper_bound": round(self.upper_bound, 2),
            "std_dev": round(self.std_dev, 2),
            "cv": round(self.cv, 4),
            "cv_label": self.cv_label,
            "outlier_count": self.outlier_count,
        }


class PriceAnalyzer:
    """
    Analyzes listing prices with IQR outlier detection.

    IQR method:
    - Q1 = 25th percentile
    - Q3 = 75th percentile
    - IQR = Q3 - Q1
    - Lower bound = Q1 - 1.5 * IQR
    - Upper bound = Q3 + 1.5 * IQR
    - Prices outside bounds are flagged as outliers
    """

    IQR_MULTIPLIER = 1.5

    def analyze(self, listings: List[dict]) -> Optional[PriceStats]:
        """
        Analyze prices from listings with outlier detection.

        Args:
            listings: List of parsed eBay listing dicts

        Returns:
            PriceStats or None if insufficient data
        """
        # Extract valid prices
        prices = []
        for listing in listings:
            try:
                price = float(listing.get("price_value", 0))
                if price > 0:
                    prices.append(price)
            except (ValueError, TypeError):
                continue

        if len(prices) < 3:
            logger.debug("Insufficient prices for analysis")
            return None

        prices.sort()

        # Calculate quartiles
        n = len(prices)
        q1 = self._percentile(prices, 25)
        q3 = self._percentile(prices, 75)
        iqr = q3 - q1

        # Bounds
        lower = q1 - self.IQR_MULTIPLIER * iqr
        upper = q3 + self.IQR_MULTIPLIER * iqr

        # Separate inliers and outliers
        inliers = [p for p in prices if lower <= p <= upper]
        outlier_count = len(prices) - len(inliers)

        if len(inliers) < 2:
            # If too many outliers removed, use all prices
            inliers = prices
            outlier_count = 0

        # Statistics on cleaned prices
        median = statistics.median(inliers)
        mean = statistics.mean(inliers)
        std_dev = statistics.stdev(inliers) if len(inliers) >= 2 else 0
        cv = std_dev / mean if mean > 0 else 0

        # CV label
        if cv < 0.15:
            cv_label = "Very Stable"
        elif cv < 0.30:
            cv_label = "Variable"
        else:
            cv_label = "Unstable"

        return PriceStats(
            count=len(prices),
            median=median,
            mean=mean,
            min_price=min(prices),
            max_price=max(prices),
            q1=q1,
            q3=q3,
            iqr=iqr,
            lower_bound=lower,
            upper_bound=upper,
            std_dev=std_dev,
            cv=cv,
            outlier_count=outlier_count,
            prices_after_outlier_removal=inliers,
            cv_label=cv_label,
        )

    def is_price_outlier(
        self,
        price: float,
        stats: PriceStats,
    ) -> bool:
        """Check if a specific price is an outlier."""
        return price < stats.lower_bound or price > stats.upper_bound

    def price_attractiveness(
        self,
        price: float,
        stats: PriceStats,
    ) -> float:
        """
        Score how attractive a price is relative to the market.

        0 = very expensive (way above median)
        50 = at median
        100 = very cheap (way below median)

        Outlier prices are capped at 20 or 80.
        """
        if stats.median == 0:
            return 50.0

        ratio = price / stats.median

        if ratio <= 0.5:
            # 50% below median — suspicious or great deal
            score = 90.0 if not self.is_price_outlier(price, stats) else 20.0
        elif ratio <= 0.8:
            score = 80.0  # below median — attractive
        elif ratio <= 1.0:
            score = 60.0  # at or slightly below median
        elif ratio <= 1.2:
            score = 40.0  # slightly above median
        elif ratio <= 1.5:
            score = 25.0  # above median
        else:
            score = 10.0 if not self.is_price_outlier(price, stats) else 5.0

        return score

    def _percentile(self, sorted_data: List[float], p: int) -> float:
        """Calculate p-th percentile of sorted data."""
        n = len(sorted_data)
        k = (n - 1) * p / 100.0
        f = int(k)
        c = f + 1
        if c >= n:
            return sorted_data[-1]
        d = k - f
        return sorted_data[f] + d * (sorted_data[c] - sorted_data[f])