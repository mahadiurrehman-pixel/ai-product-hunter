"""
Germany (DE) eBay marketplace fee rules.

Source: eBay DE fee schedule (Managed Payments).
All amounts in EUR (€).

Key DE characteristics:
- Seller types: Private / Commercial
- eBay Shop affects thresholds for some commercial categories
- FVF rates are VAT-inclusive (19% VAT already included)
- No separate per-order transaction fee specified
- International fees vary by seller type + buyer region
- FVF cap exists structurally but exact values not supplied
- PayPal fees are obsolete (Managed Payments only)
- Excluded: Motors, Real Estate, Classified Ads
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Reusable Tiered Fee Calculation
# =============================================================================

@dataclass
class FeeTier:
    """A single fee bracket tier (cumulative threshold)."""
    max_amount: Optional[float]  # None = unlimited
    rate: float


def calculate_tiered_fee(
    amount: Decimal,
    tiers: List[FeeTier],
) -> Decimal:
    """
    Calculate progressive/portion-based tiered fee.

    Example:
        tiers = [FeeTier(200, 0.065), FeeTier(None, 0.02)]
        amount = €500
        → First €200 × 6.5% = €13.00
        → Remaining €300 × 2% = €6.00
        → Total = €19.00
    """
    if amount <= 0 or not tiers:
        return Decimal("0")

    total_fee = Decimal("0")
    prev_threshold = Decimal("0")

    for tier in tiers:
        if amount <= prev_threshold:
            break

        if tier.max_amount is not None:
            current_threshold = Decimal(str(tier.max_amount))
            bracket_width = current_threshold - prev_threshold
            tier_amount = max(
                Decimal("0"), min(amount - prev_threshold, bracket_width)
            )
            prev_threshold = current_threshold
        else:
            tier_amount = max(Decimal("0"), amount - prev_threshold)

        tier_fee = tier_amount * Decimal(str(tier.rate))
        total_fee += tier_fee

    return total_fee


# =============================================================================
# Excluded Categories
# =============================================================================

DE_EXCLUDED_CATEGORIES = {"motors", "real_estate", "classified_ads"}


def is_excluded_category(category: str) -> bool:
    """Check if category is excluded from DE fee calculation."""
    return category.lower().strip().replace(" ", "_") in DE_EXCLUDED_CATEGORIES


# =============================================================================
# Private Seller FVF Rules
# =============================================================================
# Buyer in Eurozone & Sweden → 0%
# Other → 11% up to €1,990, 2% above €1,990

DE_PRIVATE_RATES = {
    "eurozone_sweden": {
        "tiers": [FeeTier(None, 0.0)],
    },
    "other": {
        "tiers": [
            FeeTier(1990, 0.11),
            FeeTier(None, 0.02),
        ],
    },
}


def get_private_rate_key(buyer_region: str) -> str:
    """Map buyer region to private rate key."""
    if buyer_region == "eurozone_sweden":
        return "eurozone_sweden"
    return "other"


# =============================================================================
# Commercial Seller FVF Rules
# =============================================================================
# Structure:
#   category → subcategory → shop/no_shop → tiers
#   "_default" subcategory is used when no specific subcategory matches

def _shop_tiers(threshold: float, rate: float) -> List[FeeTier]:
    """Helper: shop tiers with given threshold and rate."""
    return [FeeTier(threshold, rate), FeeTier(None, 0.02)]


def _noshop_tiers(rate: float) -> List[FeeTier]:
    """Helper: no-shop tiers (always €990 threshold)."""
    return [FeeTier(990, rate), FeeTier(None, 0.02)]


DE_COMMERCIAL_RATES: Dict[str, dict] = {
    # --- SIMPLE CATEGORIES (shop variation) ---
    "domestic_appliances": {
        "_default": {
            "shop": _shop_tiers(200, 0.065),
            "no_shop": _noshop_tiers(0.065),
        },
    },
    "musical_instruments": {
        "_default": {
            "shop": _shop_tiers(300, 0.11),
            "no_shop": _noshop_tiers(0.11),
        },
    },

    # --- SIMPLE CATEGORIES (no shop variation) ---
    "tickets": {
        "_default": {
            "shop": _noshop_tiers(0.09),
            "no_shop": _noshop_tiers(0.09),
        },
    },
    "garden_handyman": {
        "_default": {
            "shop": [FeeTier(200, 0.12), FeeTier(None, 0.02)],
            "no_shop": [FeeTier(200, 0.12), FeeTier(None, 0.02)],
        },
    },
    "clothing_accessories": {
        "_default": {
            "shop": _noshop_tiers(0.12),
            "no_shop": _noshop_tiers(0.12),
        },
    },

    # --- GENERAL CATCH-ALL (11% / 2%) ---
    # Covers: Other, Infant, Craft & Art Supplies, Stamps, Books,
    # Office & Stationery, Business & Industry, Gourmet, Movies & DVDs,
    # Pet Shops, Furniture & Living, Modelling, Coins, Travel, Toy, Sports
    "general": {
        "_default": {
            "shop": _noshop_tiers(0.11),
            "no_shop": _noshop_tiers(0.11),
        },
    },

    # --- NFT CATEGORIES ---
    "antiques_art": {
        "_default": {
            "shop": _noshop_tiers(0.11),
            "no_shop": _noshop_tiers(0.11),
        },
        "nft": {
            "shop": [FeeTier(None, 0.05)],
            "no_shop": [FeeTier(None, 0.05)],
        },
    },
    "movies_series": {
        "_default": {
            "shop": _noshop_tiers(0.09),
            "no_shop": _noshop_tiers(0.09),
        },
        "nft": {
            "shop": [FeeTier(None, 0.05)],
            "no_shop": [FeeTier(None, 0.05)],
        },
    },
    "music": {
        "_default": {
            "shop": _noshop_tiers(0.09),
            "no_shop": _noshop_tiers(0.09),
        },
        "nft": {
            "shop": [FeeTier(None, 0.05)],
            "no_shop": [FeeTier(None, 0.05)],
        },
    },
    "toys_hobbies": {
        "_default": {
            "shop": _noshop_tiers(0.11),
            "no_shop": _noshop_tiers(0.11),
        },
        "nft": {
            "shop": [FeeTier(None, 0.05)],
            "no_shop": [FeeTier(None, 0.05)],
        },
    },

    # --- COMPLEX CATEGORIES ---
    "automotive_parts": {
        "_default": {
            "shop": _noshop_tiers(0.12),
            "no_shop": _noshop_tiers(0.12),
        },
        "specified_electronics": {
            "shop": _shop_tiers(300, 0.065),
            "no_shop": _noshop_tiers(0.065),
        },
        "rims_wheels_tires": {
            "shop": _noshop_tiers(0.065),
            "no_shop": _noshop_tiers(0.065),
        },
        "clothing_helmets_protection": {
            "shop": _noshop_tiers(0.11),
            "no_shop": _noshop_tiers(0.11),
        },
        "chargers_wall_boxes": {
            "shop": _shop_tiers(300, 0.12),
            "no_shop": _noshop_tiers(0.065),
        },
    },
    "beauty": {
        "_default": {
            "shop": _noshop_tiers(0.11),
            "no_shop": _noshop_tiers(0.11),
        },
        "electric_hair_dental": {
            "shop": _shop_tiers(300, 0.065),
            "no_shop": _noshop_tiers(0.065),
        },
        "electrical_hair_removal": {
            "shop": [FeeTier(200, 0.11), FeeTier(None, 0.02)],
            "no_shop": [FeeTier(200, 0.11), FeeTier(None, 0.02)],
        },
    },
    "computers": {
        "_default": {
            "shop": _noshop_tiers(0.11),
            "no_shop": _noshop_tiers(0.11),
        },
        "specified_accessories": {
            "shop": _shop_tiers(200, 0.11),
            "no_shop": _noshop_tiers(0.11),
        },
        "printers_scanners": {
            "shop": _shop_tiers(200, 0.065),
            "no_shop": _noshop_tiers(0.065),
        },
    },
    "cameras": {
        "_default": {
            "shop": _shop_tiers(200, 0.11),
            "no_shop": _noshop_tiers(0.11),
        },
        "lenses_memory": {
            "shop": _shop_tiers(300, 0.065),
            "no_shop": _noshop_tiers(0.065),
        },
    },
    "mobile_phones": {
        "_default": {
            "shop": _shop_tiers(300, 0.065),
            "no_shop": _noshop_tiers(0.065),
        },
        "accessories": {
            "shop": _shop_tiers(300, 0.11),
            "no_shop": _noshop_tiers(0.11),
        },
    },
    "pc_video_games": {
        "_default": {
            "shop": _noshop_tiers(0.09),
            "no_shop": _noshop_tiers(0.09),
        },
        "equipment": {
            "shop": _shop_tiers(300, 0.11),
            "no_shop": _noshop_tiers(0.11),
        },
        "parts_consoles_memory": {
            "shop": _shop_tiers(300, 0.065),
            "no_shop": _noshop_tiers(0.065),
        },
    },
    "tv_video_audio": {
        "_default": {
            "shop": _shop_tiers(300, 0.065),
            "no_shop": _noshop_tiers(0.065),
        },
        "accessories_parts": {
            "shop": _shop_tiers(200, 0.11),
            "no_shop": _noshop_tiers(0.11),
        },
    },
    "watches_jewellery": {
        "_default": {
            "shop": _shop_tiers(400, 0.14),
            "no_shop": _noshop_tiers(0.14),
        },
        "watches_specified": {
            "shop": _shop_tiers(400, 0.11),
            "no_shop": _noshop_tiers(0.11),
        },
    },
}


def get_de_commercial_tiers(
    category: str,
    subcategory: str,
    has_shop: bool,
) -> List[FeeTier]:
    """
    Get DE commercial FVF tiers for a category/subcategory/shop combination.

    Args:
        category: Main category identifier
        subcategory: Subcategory identifier (empty for default)
        has_shop: Whether seller has eBay Shop subscription

    Returns:
        List of FeeTier for progressive calculation
    """
    cat = category.lower().strip().replace(" ", "_")
    sub = subcategory.lower().strip().replace(" ", "_")
    shop_key = "shop" if has_shop else "no_shop"

    cat_config = DE_COMMERCIAL_RATES.get(cat)
    if cat_config is None:
        cat_config = DE_COMMERCIAL_RATES["general"]

    # Try subcategory match first
    if sub and sub in cat_config:
        return cat_config[sub][shop_key]

    # Fall back to _default
    if "_default" in cat_config:
        return cat_config["_default"][shop_key]

    # Ultimate fallback
    return DE_COMMERCIAL_RATES["general"]["_default"][shop_key]


# =============================================================================
# FVF Cap (Structural Support — Values Not Supplied)
# =============================================================================

DE_FVF_CAP_CONFIGURED = False  # Exact cap values not provided in source


def apply_de_fvf_cap(
    variable_fvf: Decimal,
    category: str,
    seller_type: str,
    has_shop: bool,
) -> Tuple[Decimal, bool]:
    """
    Apply DE FVF cap if configured.

    Returns:
        Tuple of (capped_fvf, cap_was_applied)
    """
    if not DE_FVF_CAP_CONFIGURED:
        return variable_fvf, False

    # Future: implement cap lookup by category/seller/shop
    return variable_fvf, False


# =============================================================================
# International Fee Rules
# =============================================================================

DE_INTERNATIONAL_RATES = {
    "private": {
        "eurozone_sweden": 0.0,
        "europe_usa_canada": 0.0191,
        "uk": 0.0143,
        "other": 0.0393,
    },
    "commercial": {
        "eurozone_sweden": 0.0,
        "europe_usa_canada": 0.016,
        "uk": 0.012,
        "other": 0.033,
    },
}


def calculate_de_international_fee(
    sale_amount: Decimal,
    seller_type: str,
    buyer_region: str,
    overseas: bool,
) -> Decimal:
    """
    Calculate DE international fee.

    Args:
        sale_amount: Total sale amount (price + shipping)
        seller_type: "private" or "commercial"
        buyer_region: DEBuyerRegion value
        overseas: Whether selling to overseas buyers

    Returns:
        International fee amount (Decimal)
    """
    if not overseas or buyer_region == "eurozone_sweden":
        return Decimal("0")

    rates = DE_INTERNATIONAL_RATES.get(
        seller_type, DE_INTERNATIONAL_RATES["commercial"]
    )
    rate = rates.get(buyer_region, rates.get("other", 0.0))

    return sale_amount * Decimal(str(rate))


# =============================================================================
# VAT Handling
# =============================================================================

DE_VAT_RATE = 0.19  # 19% — already included in all eBay fees


# =============================================================================
# Promoted Listings & Charity
# =============================================================================
# The supplied source does not specify DE promoted/charity rules.
# These are handled by the shared calculator if configured.