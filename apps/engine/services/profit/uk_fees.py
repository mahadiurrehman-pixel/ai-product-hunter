"""
UK eBay marketplace fee rules.

Source: eBay UK fee schedule.
All amounts in GBP (£).

Key UK differences from US:
- Seller types: Private / Business (not store tiers)
- VAT treatment for business sellers (20% on eBay fees)
- FVF cap: £250 per item
- International fees vary by seller type + buyer region
- Currency conversion charge: 2.5%
- Promoted listings: ad rate × selling price (excludes postage)
- Charity: percentage × selling price (excludes shipping)
- 10p transaction fee for qualifying orders ≤ £10 (business only)
- Top Rated: 10% discount on variable FVF only
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# Bracket Calculation
# =============================================================================

@dataclass
class FeeTier:
    """A single fee bracket tier."""
    max_amount: Optional[float]  # None = unlimited
    rate: float
    fixed_fee: float = 0.0


def calculate_tiered_fee(
    amount: Decimal,
    tiers: List[FeeTier],
) -> Decimal:
    """
    Calculate progressive/portion-based tiered fee.

    Handles cumulative tier thresholds (e.g. £500, £1000, None).

    Example:
        tiers = [
            FeeTier(max_amount=1000, rate=0.069),
            FeeTier(max_amount=None, rate=0.03),
        ]
        amount = £1,500
        → First £1,000 × 6.9% = £69.00
        → Remaining £500 × 3% = £15.00
        → Total = £84.00
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
# UK FVF Cap
# =============================================================================

UK_FVF_CAP = Decimal("250")  # Maximum variable FVF per item


def apply_fvf_cap(variable_fvf: Decimal) -> Decimal:
    """Apply UK FVF cap of £250 per item."""
    return min(variable_fvf, UK_FVF_CAP)


# =============================================================================
# UK Private Seller Rates
# =============================================================================

UK_PRIVATE_RATES: Dict[str, dict] = {
    "clothing_trainers": {
        "tiers": [
            FeeTier(max_amount=100, rate=0.128),
            FeeTier(max_amount=None, rate=0.05),
        ],
        "per_order": 0.30,
    },
    "default": {
        "tiers": [
            FeeTier(max_amount=5000, rate=0.128),
            FeeTier(max_amount=None, rate=0.03),
        ],
        "per_order": 0.30,
    },
}


# =============================================================================
# UK Business Seller Rates
# =============================================================================

UK_BUSINESS_RATES: Dict[str, dict] = {
    "default": {
        "tiers": [FeeTier(max_amount=None, rate=0.129)],
        "per_order": 0.30,
    },
    "art": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "art_nfts": {
        "tiers": [FeeTier(max_amount=None, rate=0.05)],
        "per_order": 0.30,
    },
    "cameras_specified": {
        "tiers": [
            FeeTier(max_amount=1000, rate=0.069),
            FeeTier(max_amount=None, rate=0.03),
        ],
        "per_order": 0.30,
    },
    "cameras_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.099)],
        "per_order": 0.30,
    },
    "clothing_baby": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "clothing_trainers": {
        "tiers": [
            FeeTier(max_amount=100, rate=0.119),
            FeeTier(max_amount=None, rate=0.05),
        ],
        "per_order": 0.30,
        "fixed_above_threshold": 0.30,  # +£0.30 above £100
    },
    "clothing_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.099)],
        "per_order": 0.30,
    },
    "collectables_nfts": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "collectables_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "computers_specified": {
        "tiers": [
            FeeTier(max_amount=1000, rate=0.069),
            FeeTier(max_amount=None, rate=0.03),
        ],
        "per_order": 0.30,
    },
    "computers_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.099)],
        "per_order": 0.30,
    },
    "films_nfts": {
        "tiers": [FeeTier(max_amount=None, rate=0.05)],
        "per_order": 0.30,
    },
    "films_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.099)],
        "per_order": 0.30,
    },
    "garden": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "health_hair": {
        "tiers": [FeeTier(max_amount=None, rate=0.119)],
        "per_order": 0.30,
    },
    "health_smoking": {
        "tiers": [FeeTier(max_amount=None, rate=0.129)],
        "per_order": 0.30,
    },
    "health_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "home_appliances": {
        "tiers": [
            FeeTier(max_amount=400, rate=0.069),
            FeeTier(max_amount=None, rate=0.03),
        ],
        "per_order": 0.30,
    },
    "home_power_strips": {
        "tiers": [
            FeeTier(max_amount=250, rate=0.099),
            FeeTier(max_amount=None, rate=0.079),
        ],
        "per_order": 0.30,
    },
    "home_bath_furniture": {
        "tiers": [
            FeeTier(max_amount=500, rate=0.109),
            FeeTier(max_amount=1000, rate=0.079),
            FeeTier(max_amount=None, rate=0.03),
        ],
        "per_order": 0.30,
    },
    "home_other": {
        "tiers": [
            FeeTier(max_amount=500, rate=0.119),
            FeeTier(max_amount=None, rate=0.079),
        ],
        "per_order": 0.30,
    },
    "jewellery_watches": {
        "tiers": [
            FeeTier(max_amount=750, rate=0.129),
            FeeTier(max_amount=None, rate=0.02),
        ],
        "per_order": 0.30,
    },
    "jewellery_other": {
        "tiers": [
            FeeTier(max_amount=1000, rate=0.149),
            FeeTier(max_amount=None, rate=0.04),
        ],
        "per_order": 0.30,
    },
    "mobile_specified": {
        "tiers": [
            FeeTier(max_amount=400, rate=0.069),
            FeeTier(max_amount=None, rate=0.02),
        ],
        "per_order": 0.30,
    },
    "mobile_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.099)],
        "per_order": 0.30,
    },
    "music_nfts": {
        "tiers": [FeeTier(max_amount=None, rate=0.05)],
        "per_order": 0.30,
    },
    "music_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.099)],
        "per_order": 0.30,
    },
    "sound_specified": {
        "tiers": [
            FeeTier(max_amount=1000, rate=0.069),
            FeeTier(max_amount=None, rate=0.03),
        ],
        "per_order": 0.30,
    },
    "sound_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.099)],
        "per_order": 0.30,
    },
    "sports_nfts": {
        "tiers": [FeeTier(max_amount=None, rate=0.05)],
        "per_order": 0.30,
    },
    "sports_memorabilia": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "toys_nfts": {
        "tiers": [FeeTier(max_amount=None, rate=0.05)],
        "per_order": 0.30,
    },
    "toys_tents": {
        "tiers": [
            FeeTier(max_amount=250, rate=0.109),
            FeeTier(max_amount=None, rate=0.079),
        ],
        "per_order": 0.30,
    },
    "toys_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "vehicle_gps_tools": {
        "tiers": [
            FeeTier(max_amount=400, rate=0.069),
            FeeTier(max_amount=None, rate=0.03),
        ],
        "per_order": 0.30,
    },
    "vehicle_tyres": {
        "tiers": [
            FeeTier(max_amount=250, rate=0.079),
            FeeTier(max_amount=None, rate=0.03),
        ],
        "per_order": 0.30,
    },
    "vehicle_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.089)],
        "per_order": 0.30,
    },
    "video_consoles": {
        "tiers": [
            FeeTier(max_amount=400, rate=0.069),
            FeeTier(max_amount=None, rate=0.02),
        ],
        "per_order": 0.30,
    },
    "video_other": {
        "tiers": [FeeTier(max_amount=None, rate=0.099)],
        "per_order": 0.30,
    },
    # Other business categories
    "antiques": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "coins": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "dolls": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "pottery": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "stamps": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "musical_instruments": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "sporting_goods": {
        "tiers": [FeeTier(max_amount=None, rate=0.109)],
        "per_order": 0.30,
    },
    "books": {
        "tiers": [FeeTier(max_amount=None, rate=0.099)],
        "per_order": 0.30,
    },
    "music_general": {
        "tiers": [FeeTier(max_amount=None, rate=0.099)],
        "per_order": 0.30,
    },
    "business_office": {
        "tiers": [FeeTier(max_amount=None, rate=0.119)],
        "per_order": 0.30,
    },
    "memorials": {
        "tiers": [FeeTier(max_amount=None, rate=0.119)],
        "per_order": 0.30,
    },
    "crafts": {
        "tiers": [FeeTier(max_amount=None, rate=0.129)],
        "per_order": 0.30,
    },
    "event_tickets": {
        "tiers": [FeeTier(max_amount=None, rate=0.129)],
        "per_order": 0.30,
    },
    "pet_supplies": {
        "tiers": [FeeTier(max_amount=None, rate=0.129)],
        "per_order": 0.30,
    },
    "wholesale": {
        "tiers": [FeeTier(max_amount=None, rate=0.129)],
        "per_order": 0.30,
    },
    "holidays": {
        "tiers": [
            FeeTier(max_amount=650, rate=0.079),
            FeeTier(max_amount=None, rate=0.02),
        ],
        "per_order": 0.30,
    },
}

# Subcategory mapping: (category, subcategory) → rate key
UK_SUBCATEGORY_MAP: Dict[Tuple[str, str], str] = {
    ("art", "nfts"): "art_nfts",
    ("cameras", "specified"): "cameras_specified",
    ("clothing", "baby"): "clothing_baby",
    ("clothing", "trainers"): "clothing_trainers",
    ("collectables", "nfts"): "collectables_nfts",
    ("computers", "specified"): "computers_specified",
    ("films", "nfts"): "films_nfts",
    ("health", "hair"): "health_hair",
    ("health", "smoking"): "health_smoking",
    ("home", "appliances"): "home_appliances",
    ("home", "power_strips"): "home_power_strips",
    ("home", "bath_furniture"): "home_bath_furniture",
    ("jewellery", "watches"): "jewellery_watches",
    ("mobile", "specified"): "mobile_specified",
    ("music", "nfts"): "music_nfts",
    ("sound", "specified"): "sound_specified",
    ("sports", "nfts"): "sports_nfts",
    ("sports", "memorabilia"): "sports_memorabilia",
    ("toys", "nfts"): "toys_nfts",
    ("toys", "tents"): "toys_tents",
    ("vehicle", "gps_tools"): "vehicle_gps_tools",
    ("vehicle", "tyres"): "vehicle_tyres",
    ("video", "consoles"): "video_consoles",
}


def get_uk_rate_config(
    seller_type: str,
    category: str,
    subcategory: str = "",
) -> dict:
    """
    Get UK fee rate configuration.

    Args:
        seller_type: "private" or "business"
        category: Main category
        subcategory: Subcategory if applicable

    Returns:
        Rate config dict with tiers and per_order fee
    """
    cat = category.lower().strip().replace(" ", "_")
    sub = subcategory.lower().strip().replace(" ", "_")

    if seller_type == "private":
        if cat == "clothing" and sub == "trainers":
            return UK_PRIVATE_RATES["clothing_trainers"]
        return UK_PRIVATE_RATES["default"]

    # Business seller
    key = (cat, sub)
    if key in UK_SUBCATEGORY_MAP:
        rate_key = UK_SUBCATEGORY_MAP[key]
        return UK_BUSINESS_RATES.get(
            rate_key, UK_BUSINESS_RATES["default"]
        )

    # Try category-level match
    cat_key = f"{cat}_other"
    if cat_key in UK_BUSINESS_RATES:
        return UK_BUSINESS_RATES[cat_key]

    # Category-level direct match
    if cat in UK_BUSINESS_RATES:
        return UK_BUSINESS_RATES[cat]

    return UK_BUSINESS_RATES["default"]


# =============================================================================
# UK Fee Calculations
# =============================================================================

UK_TOP_RATED_DISCOUNT = 0.10  # 10% off variable FVF
UK_VAT_RATE = 0.20  # 20% VAT on eBay fees
UK_CURRENCY_CONVERSION_RATE = 0.025  # 2.5%
UK_STANDARD_TRANSACTION_FEE = Decimal("0.30")
UK_LOW_VALUE_TRANSACTION_FEE = Decimal("0.10")
UK_LOW_VALUE_THRESHOLD = Decimal("10")


def calculate_uk_fvf(
    sale_amount: Decimal,
    seller_type: str,
    category: str,
    subcategory: str = "",
    seller_level: str = "above_standard",
    num_orders: int = 1,
) -> Tuple[Decimal, Decimal, float]:
    """
    Calculate UK FVF.

    Returns:
        Tuple of (total_fvf, variable_fvf, effective_rate)
    """
    config = get_uk_rate_config(seller_type, category, subcategory)
    tiers = config["tiers"]
    per_order = Decimal(str(config.get("per_order", 0.30)))

    # Check for 10p transaction fee (business, orders ≤ £10)
    if (
        seller_type == "business"
        and sale_amount <= UK_LOW_VALUE_THRESHOLD
    ):
        per_order = UK_LOW_VALUE_TRANSACTION_FEE

    # Calculate variable FVF using tiered brackets
    variable_fvf = calculate_tiered_fee(sale_amount, tiers)

    # Apply FVF cap
    variable_fvf = apply_fvf_cap(variable_fvf)

    # Apply Top Rated discount to variable FVF only
    effective_rate = 0.0
    if tiers:
        effective_rate = tiers[0].rate  # Base rate for reporting
    if seller_level == "top_rated":
        variable_fvf = variable_fvf * Decimal(str(1.0 - UK_TOP_RATED_DISCOUNT))
        effective_rate = effective_rate * (1.0 - UK_TOP_RATED_DISCOUNT)

    # Total FVF = variable + transaction fees
    transaction_total = per_order * num_orders
    total_fvf = variable_fvf + transaction_total

    return total_fvf, variable_fvf, effective_rate


def calculate_uk_international_fee(
    sale_amount: Decimal,
    seller_type: str,
    buyer_region: str,
    overseas: bool,
) -> Decimal:
    """
    Calculate UK international fee.

    Private: 3% for all regions
    Business: varies by region
    """
    if not overseas or buyer_region == "domestic":
        return Decimal("0")

    if seller_type == "private":
        rate = 0.03  # 3% for all private international
    else:
        region_rates = {
            "eurozone_northern_europe": 0.005,
            "us_canada": 0.018,
            "other": 0.02,
        }
        rate = region_rates.get(buyer_region, 0.02)

    return sale_amount * Decimal(str(rate))


def calculate_uk_promoted_fee(
    selling_price: Decimal,
    promoted_rate: float,
) -> Decimal:
    """
    UK promoted listings fee.

    UK rule: ad rate × selling price EXCLUDING postage.
    Valid range: 1%-20%, increments of 0.1%.
    """
    if promoted_rate <= 0:
        return Decimal("0")

    # Validate range
    if promoted_rate < 1.0 or promoted_rate > 20.0:
        logger.warning(
            f"UK promoted rate {promoted_rate}% outside 1-20% range"
        )

    return selling_price * Decimal(str(promoted_rate / 100.0))


def calculate_uk_charity(
    selling_price: Decimal,
    charity_percent: float,
) -> Decimal:
    """
    UK charity donation.

    UK rule: percentage × selling price EXCLUDING shipping.
    Valid range: 10%-100%.
    """
    if charity_percent <= 0:
        return Decimal("0")

    if charity_percent < 10.0 or charity_percent > 100.0:
        logger.warning(
            f"UK charity percent {charity_percent}% outside 10-100% range"
        )

    return selling_price * Decimal(str(charity_percent / 100.0))


def calculate_uk_vat_on_fees(
    total_ebay_fees: Decimal,
    vat_registered: bool,
    seller_type: str,
) -> Decimal:
    """
    Calculate VAT on eBay fees for UK business sellers.

    Only applies to VAT-registered business sellers.
    20% VAT on applicable eBay fees.
    """
    if seller_type != "business" or not vat_registered:
        return Decimal("0")

    return total_ebay_fees * Decimal(str(UK_VAT_RATE))


def calculate_uk_currency_conversion(
    total_payout: Decimal,
    currency_conversion: bool,
) -> Decimal:
    """
    UK currency conversion charge.

    2.5% when eBay converts seller funds to another currency.
    """
    if not currency_conversion:
        return Decimal("0")

    return total_payout * Decimal(str(UK_CURRENCY_CONVERSION_RATE))