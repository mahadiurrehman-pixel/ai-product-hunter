"""
Unified Marketplace Abstraction for REHU.

Provides a canonical Marketplace enum across all service layers
(eBay, Profit, Policy, Pipeline). Bridges simple country codes
("US", "UK", "DE", "AU", "CA") to eBay-specific identifiers.
"""
from enum import Enum
from typing import Union

from services.ebay.marketplace import EbayMarketplace


class Marketplace(str, Enum):
    """Canonical marketplace identifiers."""
    US = "US"
    UK = "UK"
    DE = "DE"
    AU = "AU"
    CA = "CA"


# =============================================================================
# Dynamic mapping built from actual EbayMarketplace members.
# Maps eBay string values (e.g., "EBAY_US", "EBAY_GB") to canonical Marketplace.
# This avoids AttributeError if the enum member names differ from expectations.
# =============================================================================

_EBAY_VALUE_TO_CANONICAL = {
    "EBAY_US": Marketplace.US,
    "EBAY_GB": Marketplace.UK,
    "EBAY_DE": Marketplace.DE,
    "EBAY_AU": Marketplace.AU,
    "EBAY_CA": Marketplace.CA,
}

# Build forward and reverse maps from actual enum members
_CANONICAL_TO_EBAY = {}
_EBAY_TO_CANONICAL = {}

for _member in EbayMarketplace:
    _canonical = _EBAY_VALUE_TO_CANONICAL.get(_member.value)
    if _canonical is not None:
        _CANONICAL_TO_EBAY[_canonical] = _member
        _EBAY_TO_CANONICAL[_member] = _canonical


def to_ebay_marketplace(marketplace: Union[str, Marketplace]) -> EbayMarketplace:
    """
    Convert a unified Marketplace (or string) to EbayMarketplace enum.

    Args:
        marketplace: Marketplace enum instance or string (e.g., "US", "UK")

    Returns:
        EbayMarketplace enum instance (e.g., EbayMarketplace.US)

    Raises:
        ValueError: If marketplace is invalid or unsupported
    """
    canon = validate_marketplace(marketplace)
    ebay = _CANONICAL_TO_EBAY.get(canon)
    if ebay is None:
        raise ValueError(
            f"Marketplace '{canon.value}' has no corresponding EbayMarketplace. "
            f"Available eBay marketplaces: {[m.value for m in EbayMarketplace]}"
        )
    return ebay


def from_ebay_marketplace(ebay_marketplace: EbayMarketplace) -> Marketplace:
    """
    Convert an EbayMarketplace enum to canonical Marketplace enum.

    Args:
        ebay_marketplace: EbayMarketplace instance

    Returns:
        Marketplace enum instance
    """
    canon = _EBAY_TO_CANONICAL.get(ebay_marketplace)
    if canon is None:
        raise ValueError(
            f"Unknown EbayMarketplace: {ebay_marketplace}. "
            f"Known mappings: {list(_EBAY_TO_CANONICAL.keys())}"
        )
    return canon


def validate_marketplace(value: Union[str, Marketplace, EbayMarketplace]) -> Marketplace:
    """
    Validate and convert any marketplace representation to a canonical Marketplace enum.

    Supports:
    - Marketplace instance
    - EbayMarketplace instance
    - Country codes: "US", "UK", "DE", "AU", "CA" (case-insensitive)
    - eBay IDs: "EBAY_US", "EBAY_GB", "EBAY_DE", "EBAY_AU", "EBAY_CA"

    Returns:
        Marketplace instance

    Raises:
        ValueError: If value is not a valid/supported marketplace
    """
    if isinstance(value, Marketplace):
        return value

    if isinstance(value, EbayMarketplace):
        return from_ebay_marketplace(value)

    if not isinstance(value, str):
        raise ValueError(
            f"Marketplace must be a string or Marketplace enum, got {type(value).__name__}"
        )

    cleaned = value.strip().upper()

    # Direct canonical lookup ("US", "UK", etc.)
    try:
        return Marketplace(cleaned)
    except ValueError:
        pass

    # eBay marketplace ID lookup ("EBAY_US", "EBAY_GB", etc.)
    canonical = _EBAY_VALUE_TO_CANONICAL.get(cleaned)
    if canonical is not None:
        # Verify the eBay enum actually has this member
        try:
            EbayMarketplace(cleaned)
            return canonical
        except ValueError:
            pass

    valid_options = [m.value for m in Marketplace]
    raise ValueError(
        f"Invalid marketplace '{value}'. Supported: {valid_options}"
    )