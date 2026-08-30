"""
Marketplace-specific policy configuration.

Different eBay marketplaces have different thresholds and enforcement
practices. This module centralizes marketplace-aware overrides so the
single PolicyChecker can adapt behavior per marketplace without
requiring separate checker classes.

IMPORTANT: The values below are illustrative defaults. Actual eBay
thresholds vary by marketplace and change over time. Verify against
current eBay policy pages before treating as authoritative.
"""
from typing import Dict


# Marketplace-specific policy configuration.
# Each marketplace can adjust:
#   - Whether specific rule categories apply
#   - Severity multipliers
#   - Additional marketplace-specific keywords (extension point)
MARKETPLACE_CONFIG: Dict[str, dict] = {
    "EBAY_US": {
        "seller_feedback_threshold_medium": 95.0,
        "seller_feedback_threshold_high": 90.0,
        "handling_time_max_expected_days": 30,
    },
    "EBAY_GB": {
        "seller_feedback_threshold_medium": 95.0,
        "seller_feedback_threshold_high": 90.0,
        "handling_time_max_expected_days": 30,
    },
    "EBAY_DE": {
        "seller_feedback_threshold_medium": 95.0,
        "seller_feedback_threshold_high": 90.0,
        "handling_time_max_expected_days": 30,
    },
    "EBAY_AU": {
        "seller_feedback_threshold_medium": 95.0,
        "seller_feedback_threshold_high": 90.0,
        "handling_time_max_expected_days": 30,
    },
    "EBAY_CA": {
        "seller_feedback_threshold_medium": 95.0,
        "seller_feedback_threshold_high": 90.0,
        "handling_time_max_expected_days": 30,
    },
}


def get_marketplace_config(marketplace: str) -> dict:
    """
    Get configuration for a marketplace.

    Falls back to EBAY_US config if marketplace not explicitly configured
    (safe default — no rules are skipped, just uses standard thresholds).

    Args:
        marketplace: eBay marketplace ID (e.g. "EBAY_US")

    Returns:
        Configuration dictionary
    """
    return MARKETPLACE_CONFIG.get(marketplace, MARKETPLACE_CONFIG["EBAY_US"])