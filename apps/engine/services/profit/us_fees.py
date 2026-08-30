"""
US eBay marketplace fee rules.

Structured configuration of US-specific fee rules including:
- Category-specific FVF rates
- Store subscriber discounts
- Top Rated Seller discount
- International fee
- Per-order transaction fees

Source: eBay US fee schedule (2024).
These rules are isolated here so other marketplaces can be
added later without modifying the core calculator.
"""
from decimal import Decimal
from typing import Dict, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# US FVF Rates by Category
# =============================================================================
# Format: {category: {"rate": float, "per_order": float,
#                      "bracket_threshold": float (optional),
#                      "bracket_rate": float (optional)}}
#
# "rate" is the base FVF percentage (e.g., 0.129 = 12.9%)
# "per_order" is the fixed per-order fee
# "bracket_threshold" and "bracket_rate" handle tiered categories
#   (e.g., Jewelry: 14.9% up to $2,500, then 5.0% above)

US_CATEGORY_RATES: Dict[str, dict] = {
    "default": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "books": {
        "rate": 0.149,
        "per_order": 0.30,
    },
    "jewelry": {
        "rate": 0.149,
        "per_order": 0.30,
        "bracket_threshold": 2500.0,
        "bracket_rate": 0.05,
    },
    "computers": {
        "rate": 0.07,
        "per_order": 0.30,
    },
    "consumer_electronics": {
        "rate": 0.08,
        "per_order": 0.30,
    },
    "musical_instruments": {
        "rate": 0.08,
        "per_order": 0.30,
    },
    "clothing": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "sporting_goods": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "toys": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "video_games": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "business_industrial": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "home_garden": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "auto_parts": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "health_beauty": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "pet_supplies": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "crafts": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "collectibles": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "antiques": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "coins": {
        "rate": 0.129,
        "per_order": 0.30,
    },
    "cameras": {
        "rate": 0.08,
        "per_order": 0.30,
    },
}

# =============================================================================
# Store Subscriber Discounts
# =============================================================================
# Discount applied to the FVF rate (multiplicative).
# e.g., Basic 1% discount → effective_rate = base_rate × 0.99

STORE_DISCOUNTS = {
    "no_store": 0.0,
    "starter": 0.0,
    "basic": 0.01,
    "premium": 0.04,
    "anchor": 0.06,
    "enterprise": 0.07,
}

# =============================================================================
# Top Rated Seller Discount
# =============================================================================
# Additional 10% discount on FVF rate for Top Rated Sellers.
# Applied multiplicatively after store discount.
# Does NOT apply to categories where eBay excludes it.

TOP_RATED_DISCOUNT = 0.10

# Categories excluded from Top Rated discount
TOP_RATED_EXCLUDED_CATEGORIES = {
    "jewelry",  # High-value jewelry excluded in some tiers
}

# =============================================================================
# International Fee
# =============================================================================
# Applied when seller sells to overseas buyers.

INTERNATIONAL_FEE_RATE = 0.0165  # 1.65% of total sale amount

# =============================================================================
# Per-Order Transaction Fee
# =============================================================================
# Fixed fee per order (separate from FVF percentage).

DEFAULT_PER_ORDER_FEE = 0.30


def get_category_rate(category: str) -> dict:
    """
    Get FVF rate configuration for a category.

    Falls back to "default" if category not found.

    Args:
        category: Category identifier string

    Returns:
        Dict with rate, per_order, and optional bracket info
    """
    cat = category.lower().strip().replace(" ", "_")
    return US_CATEGORY_RATES.get(cat, US_CATEGORY_RATES["default"])


def calculate_fvf(
    sale_amount: Decimal,
    category: str = "default",
    store_type: str = "no_store",
    seller_level: str = "above_standard",
    num_orders: int = 1,
) -> Tuple[Decimal, float]:
    """
    Calculate eBay Final Value Fee for US marketplace.

    Handles:
    - Category-specific rates
    - Price brackets (e.g., Jewelry > $2,500)
    - Store subscriber discounts
    - Top Rated Seller discount
    - Per-order transaction fees

    Args:
        sale_amount: Total sale amount per item (price + shipping)
        category: Item category
        store_type: Store subscription type
        seller_level: Seller performance level
        num_orders: Number of orders

    Returns:
        Tuple of (total_fvf, effective_rate)
    """
    rate_config = get_category_rate(category)
    base_rate = rate_config["rate"]
    per_order = Decimal(str(rate_config.get("per_order", DEFAULT_PER_ORDER_FEE)))

    # Apply store discount
    store_discount = STORE_DISCOUNTS.get(store_type, 0.0)
    effective_rate = base_rate * (1.0 - store_discount)

    # Apply Top Rated discount (if applicable)
    cat_key = category.lower().strip().replace(" ", "_")
    if (
        seller_level == "top_rated"
        and cat_key not in TOP_RATED_EXCLUDED_CATEGORIES
    ):
        effective_rate = effective_rate * (1.0 - TOP_RATED_DISCOUNT)

    # Calculate FVF with optional bracket
    bracket_threshold = rate_config.get("bracket_threshold")
    bracket_rate = rate_config.get("bracket_rate")

    if bracket_threshold and bracket_rate and sale_amount > bracket_threshold:
        # Tiered calculation
        amount_below = Decimal(str(bracket_threshold))
        amount_above = sale_amount - amount_below
        bracket_effective = bracket_rate * (1.0 - store_discount)
        if seller_level == "top_rated" and cat_key not in TOP_RATED_EXCLUDED_CATEGORIES:
            bracket_effective = bracket_effective * (1.0 - TOP_RATED_DISCOUNT)

        fvf = (amount_below * Decimal(str(effective_rate))) + (
            amount_above * Decimal(str(bracket_effective))
        )
    else:
        fvf = sale_amount * Decimal(str(effective_rate))

    # Add per-order fees
    total_fvf = fvf + (per_order * num_orders)

    return total_fvf, effective_rate


def calculate_international_fee(
    sale_amount: Decimal,
    overseas: bool,
) -> Decimal:
    """
    Calculate US international fee.

    Args:
        sale_amount: Total sale amount (price + shipping + tax if applicable)
        overseas: Whether selling to overseas buyers

    Returns:
        International fee amount (Decimal)
    """
    if not overseas:
        return Decimal("0")
    return sale_amount * Decimal(str(INTERNATIONAL_FEE_RATE))


def calculate_promoted_fee(
    promoted_base: Decimal,
    promoted_rate: float,
) -> Decimal:
    """
    Calculate promoted listings fee.

    The promoted fee is calculated on the total sale amount
    including postage and applicable sales tax.

    Args:
        promoted_base: Total sale amount (price + shipping + tax)
        promoted_rate: Promoted ad rate as percentage (e.g., 10.0)

    Returns:
        Promoted fee amount (Decimal)
    """
    if promoted_rate <= 0:
        return Decimal("0")
    return promoted_base * Decimal(str(promoted_rate / 100.0))


def calculate_charity_cost(
    sale_price: Decimal,
    charity_percent: float,
    num_orders: int = 1,
) -> Decimal:
    """
    Calculate charity donation cost.

    Args:
        sale_price: Per-item sale price
        charity_percent: Charity percentage (e.g., 10.0)
        num_orders: Number of orders

    Returns:
        Total charity cost (Decimal)
    """
    if charity_percent <= 0:
        return Decimal("0")
    total_sale = sale_price * num_orders
    return total_sale * Decimal(str(charity_percent / 100.0))