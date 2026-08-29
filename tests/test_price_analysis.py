"""Tests for PriceAnalyzer with IQR outlier detection."""
from decimal import Decimal

import pytest

from services.search.price_analysis import PriceAnalyzer


class TestPriceAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return PriceAnalyzer()

    def _listings(self, prices):
        return [{"price_value": Decimal(str(p))} for p in prices]

    def test_basic_analysis(self, analyzer):
        listings = self._listings([20, 25, 30, 35, 40])
        stats = analyzer.analyze(listings)
        assert stats is not None
        assert stats.median == 30.0
        assert stats.count == 5

    def test_outlier_detection(self, analyzer):
        # Most prices 20-40, one outlier at 500
        listings = self._listings([20, 25, 30, 35, 40, 500])
        stats = analyzer.analyze(listings)
        assert stats.outlier_count >= 1
        assert 500 not in stats.prices_after_outlier_removal

    def test_low_outlier_detection(self, analyzer):
        # Most prices 20-40, one outlier at 1
        listings = self._listings([1, 20, 25, 30, 35, 40])
        stats = analyzer.analyze(listings)
        assert stats.outlier_count >= 1

    def test_no_outliers(self, analyzer):
        listings = self._listings([29, 30, 31, 30, 29, 31])
        stats = analyzer.analyze(listings)
        assert stats.outlier_count == 0

    def test_insufficient_data(self, analyzer):
        listings = self._listings([30, 35])
        stats = analyzer.analyze(listings)
        assert stats is None

    def test_invalid_prices_skipped(self, analyzer):
        listings = [
            {"price_value": Decimal("30")},
            {"price_value": None},
            {"price_value": Decimal("-10")},
            {"price_value": Decimal("0")},
            {"price_value": Decimal("35")},
            {"price_value": Decimal("32")},
        ]
        stats = analyzer.analyze(listings)
        assert stats is not None
        assert stats.count == 3  # only 30, 35, 32

    def test_cv_stable(self, analyzer):
        listings = self._listings([30.0, 30.1, 29.9, 30.0, 30.2])
        stats = analyzer.analyze(listings)
        assert stats.cv < 0.15
        assert stats.cv_label == "Very Stable"

    def test_cv_variable(self, analyzer):
        listings = self._listings([20, 30, 40, 25, 35])
        stats = analyzer.analyze(listings)
        assert stats.cv_label in ("Variable", "Unstable")

    def test_price_attractiveness_below_median(self, analyzer):
        listings = self._listings([20, 25, 30, 35, 40])
        stats = analyzer.analyze(listings)
        score = analyzer.price_attractiveness(22.0, stats)
        assert score > 50  # below median = attractive

    def test_price_attractiveness_above_median(self, analyzer):
        listings = self._listings([20, 25, 30, 35, 40])
        stats = analyzer.analyze(listings)
        score = analyzer.price_attractiveness(38.0, stats)
        assert score < 50  # above median = less attractive

    def test_is_outlier(self, analyzer):
        listings = self._listings([20, 25, 30, 35, 40])
        stats = analyzer.analyze(listings)
        assert analyzer.is_price_outlier(500.0, stats) is True
        assert analyzer.is_price_outlier(30.0, stats) is False

    def test_to_dict(self, analyzer):
        listings = self._listings([20, 25, 30, 35, 40])
        stats = analyzer.analyze(listings)
        d = stats.to_dict()
        assert "median" in d
        assert "cv" in d
        assert "outlier_count" in d
        assert "cv_label" in d