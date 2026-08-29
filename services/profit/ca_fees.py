"""
Canada (CA) eBay marketplace fee rules.

Source: eBay CA fee schedule (Managed Payments).
All amounts in CAD ($).

Key CA characteristics:
- Store types: No Store, Basic, Premium, Anchor
- Basic/Premium/Anchor share the same FVF structure
- Progressive category-specific thresholds
- Seller level adjustments: Top Rated -10%, Below Average +5%
- International fee: Domestic 0%, US 0.4%, Other 1.0%
- FVF base: item price + shipping + tax (Managed Payments total)
- Athletic Shoes: FVF calculated on sold price ONLY (no shipping)
- Transaction fee: NOT specified in source
- Promoted listings base: NOT specified in source
- Charity rule: NOT specified in source
- Currency conversion: NOT specified in source
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Store Type Constants
# =============================================================================

CA_STORE_NO = "no_store"
CA_STORE_BASIC = "basic"
CA_STORE_PREMIUM = "premium"
CA_STORE_ANCHOR = "anchor"

CA_STORE_TYPES = {
    CA_STORE_NO, CA_STORE_BASIC, CA_STORE_PREMIUM, CA_STORE_ANCHOR
}


def is_store_seller(store_type: str) -> bool:
    return store_type in (CA_STORE_BASIC, CA_STORE_PREMIUM, CA_STORE_ANCHOR)


# =============================================================================
# International Destination Constants
# =============================================================================

CA_DEST_DOMESTIC = "domestic"
CA_DEST_US = "us"
CA_DEST_OTHER = "other_international"


# =============================================================================
# Reusable Progressive Fee Calculation
# =============================================================================

@dataclass
class FeeTier:
    """Cumulative threshold tier."""
    max_amount: Optional[float]  # None = unlimited
    rate: float


def calculate_progressive_fee(
    amount: Decimal, tiers: List[FeeTier]
) -> Decimal:
    """
    Progressive portion-based fee.

    Example:
        tiers = [FeeTier(2500, 0.1235), FeeTier(None, 0.0235)]
        amount = $3,000
        → $2,500 × 12.35% = $308.75
        → $500 × 2.35%    = $11.75
        → Total = $320.50
    """
    if amount <= 0 or not tiers:
        return Decimal("0")

    total = Decimal("0")
    prev = Decimal("0")

    for tier in tiers:
        if amount <= prev:
            break
        if tier.max_amount is not None:
            threshold = Decimal(str(tier.max_amount))
            width = threshold - prev
            portion = max(Decimal("0"), min(amount - prev, width))
            prev = threshold
        else:
            portion = max(Decimal("0"), amount - prev)
        total += portion * Decimal(str(tier.rate))

    return total


# =============================================================================
# Rule Match Result
# =============================================================================

@dataclass
class CARuleMatch:
    """Result of category rule resolution."""
    tiers: List[FeeTier]
    fvf_base_uses_shipping: bool = True
    is_specific_match: bool = True
    rule_name: str = ""


# =============================================================================
# NFT (Flat 5%) Categories
# =============================================================================

NFT_SUBCATEGORIES = {
    "art_nft", "art_nfts",
    "emerging_nfts", "non_sport_trading_card_nfts",
    "movie_nfts", "music_nfts",
    "sport_trading_card_nfts", "ccg_nfts", "nft",
}

def _nft_match(rule_name: str) -> CARuleMatch:
    return CARuleMatch(
        tiers=[FeeTier(None, 0.05)],
        rule_name=rule_name,
    )


# =============================================================================
# NO STORE FVF Rules
# =============================================================================

def resolve_no_store_rule(
    category: str, subcategory: str
) -> CARuleMatch:
    """Resolve FVF rule for No Store sellers."""
    cat = _norm(category)
    sub = _norm(subcategory)

    # NFT — flat 5%
    if sub in NFT_SUBCATEGORIES:
        return _nft_match(f"nostore_nft_{sub}")

    # Business & Industrial — special categories
    if cat == "business_industrial":
        if sub in ("heavy_equipment", "commercial_printing_presses",
                   "food_trucks"):
            return CARuleMatch(
                tiers=[FeeTier(14999.99, 0.03), FeeTier(None, 0.005)],
                rule_name="nostore_business_industrial_heavy",
            )

    # Clothing — Athletic Shoes (sold price only)
    if cat in ("clothing", "clothing_shoes_accessories"):
        if sub in ("mens_athletic_shoes", "womens_athletic_shoes",
                   "athletic_shoes"):
            return CARuleMatch(
                tiers=[FeeTier(149.99, 0.1325), FeeTier(None, 0.08)],
                fvf_base_uses_shipping=False,
                rule_name="nostore_athletic_shoes",
            )

    # Collectibles — Non-Sport Trading Cards
    if cat == "collectibles":
        if sub == "non_sport_trading_cards":
            return CARuleMatch(
                tiers=[FeeTier(7499.99, 0.129), FeeTier(None, 0.0235)],
                rule_name="nostore_non_sport_trading_cards",
            )

    # Musical Instruments — Guitars & Basses
    if cat == "musical_instruments":
        if sub == "guitars_basses":
            return CARuleMatch(
                tiers=[FeeTier(7499.99, 0.0635), FeeTier(None, 0.0235)],
                rule_name="nostore_guitars_basses",
            )

    # Sports — Sports Trading Cards
    if cat in ("sports", "sports_mem"):
        if sub == "sports_trading_cards":
            return CARuleMatch(
                tiers=[FeeTier(7499.99, 0.129), FeeTier(None, 0.0235)],
                rule_name="nostore_sports_trading_cards",
            )

    # Toys — Collectible Card Games
    if cat == "toys_hobbies":
        if sub == "collectible_card_games":
            return CARuleMatch(
                tiers=[FeeTier(7499.99, 0.129), FeeTier(None, 0.0235)],
                rule_name="nostore_collectible_card_games",
            )

    # Everything Else
    return CARuleMatch(
        tiers=[FeeTier(7499.99, 0.1325), FeeTier(None, 0.0235)],
        is_specific_match=False,
        rule_name="nostore_everything_else",
    )


# =============================================================================
# STORE FVF Rules (Basic/Premium/Anchor share the same rules)
# =============================================================================

GENERAL_CATEGORIES = {
    "everything_else", "antiques", "baby", "crafts",
    "dolls_bears", "entertainment_memorabilia",
    "health_beauty", "home_garden",
    "jewellery_watches", "jewelry_watches",
    "pet_supplies", "pottery_glass",
    "specialty_services", "sporting_goods",
}


def resolve_store_rule(
    category: str, subcategory: str
) -> CARuleMatch:
    """Resolve FVF rule for Basic/Premium/Anchor store sellers."""
    cat = _norm(category)
    sub = _norm(subcategory)

    # NFT — flat 5%
    if sub in NFT_SUBCATEGORIES:
        return _nft_match(f"store_nft_{sub}")

    # Books & Magazines
    if cat in ("books_magazines", "books"):
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.1325), FeeTier(None, 0.0235)],
            rule_name="store_books",
        )

    # Art (excluding NFT)
    if cat == "art":
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
            rule_name="store_art",
        )

    # Business & Industrial
    if cat == "business_industrial":
        if sub in ("heavy_equipment", "commercial_printing_presses",
                   "food_trucks"):
            return CARuleMatch(
                tiers=[FeeTier(15000, 0.025), FeeTier(None, 0.005)],
                rule_name="store_business_heavy",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
            rule_name="store_business_general",
        )

    # Cameras & Photo
    if cat in ("cameras_photo", "cameras"):
        if sub in ("accessories", "drone_parts", "other_cameras",
                   "replacement_parts"):
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
                rule_name="store_cameras_accessories",
            )
        if sub == "memory_cards":
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.09), FeeTier(None, 0.0235)],
                rule_name="store_cameras_memory",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.09), FeeTier(None, 0.0235)],
            rule_name="store_cameras_default",
        )

    # Cell Phones & Accessories
    if cat in ("cell_phones", "cell_phones_accessories"):
        if sub == "memory_cards":
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.09), FeeTier(None, 0.0235)],
                rule_name="store_cell_memory",
            )
        if sub == "accessories":
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
                rule_name="store_cell_accessories",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.09), FeeTier(None, 0.0235)],
            rule_name="store_cell_default",
        )

    # Clothing — Athletic Shoes (sold price only)
    if cat in ("clothing", "clothing_shoes_accessories"):
        if sub in ("mens_athletic_shoes", "womens_athletic_shoes",
                   "athletic_shoes"):
            return CARuleMatch(
                tiers=[FeeTier(149.99, 0.1235), FeeTier(None, 0.07)],
                fvf_base_uses_shipping=False,
                rule_name="store_athletic_shoes",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
            rule_name="store_clothing",
        )

    # Coins & Paper Money
    if cat in ("coins", "coins_paper_money"):
        if sub == "bullion":
            return CARuleMatch(
                tiers=[
                    FeeTier(1500, 0.0735),
                    FeeTier(10000, 0.05),
                    FeeTier(None, 0.045),
                ],
                rule_name="store_bullion",
            )
        return CARuleMatch(
            tiers=[FeeTier(4000, 0.09), FeeTier(None, 0.0235)],
            rule_name="store_coins",
        )

    # Collectibles
    if cat == "collectibles":
        if sub == "non_sport_trading_cards":
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.12), FeeTier(None, 0.0235)],
                rule_name="store_non_sport_cards",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
            rule_name="store_collectibles",
        )

    # Computers/Tablets & Networking
    if cat in ("computers", "computers_tablets_networking"):
        if sub in ("cpus", "desktops", "hard_drives", "laptops",
                   "memory_ram", "monitors", "motherboards",
                   "motherboards_combos", "printers", "tablets"):
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.07), FeeTier(None, 0.0235)],
                rule_name="store_computers_hardware",
            )
        if sub in ("3d_printer_consumables", "3d_printer_parts",
                   "cables_connectors", "keyboards_mice",
                   "laptop_accessories", "other_computers",
                   "power_protection", "tablet_accessories"):
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
                rule_name="store_computers_accessories",
            )
        if sub == "tablet_memory_usb":
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.09), FeeTier(None, 0.0235)],
                rule_name="store_tablet_memory",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.09), FeeTier(None, 0.0235)],
            rule_name="store_computers_default",
        )

    # Consumer Electronics
    if cat == "consumer_electronics":
        if sub in ("multipurpose_batteries", "portable_audio_accessories",
                   "tv_video_audio_accessories", "tv_video_audio_parts",
                   "car_electronics_accessories", "gps_accessories",
                   "vr_cases", "vr_other_accessories", "vr_parts"):
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
                rule_name="store_electronics_accessories",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.09), FeeTier(None, 0.0235)],
            rule_name="store_electronics_default",
        )

    # Motors (parts/accessories only)
    if cat in ("motors", "ebay_motors"):
        if sub in ("tires", "tires_wheels"):
            return CARuleMatch(
                tiers=[FeeTier(1000, 0.09), FeeTier(None, 0.0235)],
                rule_name="store_motors_tires",
            )
        if sub in ("automotive_tools", "parts_accessories",
                   "safety_security"):
            return CARuleMatch(
                tiers=[FeeTier(1000, 0.1135), FeeTier(None, 0.0235)],
                rule_name="store_motors_parts",
            )
        if sub == "apparel_protective_gear":
            return CARuleMatch(
                tiers=[FeeTier(1000, 0.1235), FeeTier(None, 0.0235)],
                rule_name="store_motors_apparel",
            )
        return CARuleMatch(
            tiers=[FeeTier(1000, 0.1135), FeeTier(None, 0.0235)],
            is_specific_match=False,
            rule_name="store_motors_fallback",
        )

    # Movies & TV
    if cat in ("movies_tv", "movies"):
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.1325), FeeTier(None, 0.0235)],
            rule_name="store_movies",
        )

    # Music
    if cat == "music":
        if sub == "vinyl_records":
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
                rule_name="store_music_vinyl",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.1325), FeeTier(None, 0.0235)],
            rule_name="store_music_default",
        )

    # Musical Instruments & Gear
    if cat == "musical_instruments":
        if sub == "guitars_basses":
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.0635), FeeTier(None, 0.0235)],
                rule_name="store_guitars_basses",
            )
        if sub in ("dj_equipment", "pro_audio"):
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.09), FeeTier(None, 0.0235)],
                rule_name="store_musical_pro",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.10), FeeTier(None, 0.0235)],
            rule_name="store_musical_default",
        )

    # Sports
    if cat in ("sports", "sports_mem"):
        if sub == "sports_trading_cards":
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.12), FeeTier(None, 0.0235)],
                rule_name="store_sports_cards",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
            rule_name="store_sports_default",
        )

    # Toys & Hobbies
    if cat == "toys_hobbies":
        if sub == "collectible_card_games":
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.12), FeeTier(None, 0.0235)],
                rule_name="store_toys_ccg",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
            rule_name="store_toys_default",
        )

    # Video Games & Consoles
    if cat in ("video_games", "video_games_consoles"):
        if sub == "consoles":
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.07), FeeTier(None, 0.0235)],
                rule_name="store_video_consoles",
            )
        if sub in ("replacement_parts", "video_game_accessories",
                   "video_games"):
            return CARuleMatch(
                tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
                rule_name="store_video_accessories",
            )
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.09), FeeTier(None, 0.0235)],
            rule_name="store_video_default",
        )

    # General categories fallback
    if cat in GENERAL_CATEGORIES:
        return CARuleMatch(
            tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
            rule_name="store_general",
        )

    # Ultimate fallback
    return CARuleMatch(
        tiers=[FeeTier(2500, 0.1235), FeeTier(None, 0.0235)],
        is_specific_match=False,
        rule_name="store_fallback",
    )


def resolve_ca_rule(
    store_type: str, category: str, subcategory: str
) -> CARuleMatch:
    """Resolve FVF rule for any Canada seller."""
    if store_type == CA_STORE_NO:
        return resolve_no_store_rule(category, subcategory)
    return resolve_store_rule(category, subcategory)


# =============================================================================
# Seller Level Adjustments
# =============================================================================

CA_TOP_RATED_DISCOUNT = Decimal("0.10")     # 10% off FVF
CA_BELOW_AVERAGE_SURCHARGE = Decimal("0.05")  # 5% extra FVF


def apply_seller_level_adjustment(
    fvf: Decimal, seller_level: str
) -> Decimal:
    if seller_level == "top_rated":
        return fvf * (Decimal("1") - CA_TOP_RATED_DISCOUNT)
    if seller_level in ("below_standard", "below_average"):
        return fvf * (Decimal("1") + CA_BELOW_AVERAGE_SURCHARGE)
    return fvf  # above_standard: no adjustment


# =============================================================================
# International Fee
# =============================================================================

CA_INTL_RATE_US = Decimal("0.004")     # 0.4%
CA_INTL_RATE_OTHER = Decimal("0.010")  # 1.0%


def calculate_ca_international_fee(
    sale_amount: Decimal,
    destination: str,
) -> Decimal:
    if destination == CA_DEST_US:
        return sale_amount * CA_INTL_RATE_US
    if destination == CA_DEST_OTHER:
        return sale_amount * CA_INTL_RATE_OTHER
    return Decimal("0")


# =============================================================================
# Helper: normalize category strings
# =============================================================================

def _norm(value: str) -> str:
    """Normalize a category/subcategory string."""
    if not value:
        return ""
    return (
        value.lower()
        .strip()
        .replace(" ", "_")
        .replace("&", "")
        .replace(",", "")
        .replace("__", "_")
    )