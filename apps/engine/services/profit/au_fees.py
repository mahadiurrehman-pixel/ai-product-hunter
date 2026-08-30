"""
Australia (AU) eBay marketplace fee rules.

Source: eBay AU fee schedule (Managed Payments).
All amounts in AUD ($).

Key AU characteristics:
- Store types: No Store, Basic, Featured, Anchor
- Progressive threshold: first $4,000 at category rate, above at 2.5%
- No Store fees include GST
- Basic/Featured/Anchor without ABN: +10% GST on eBay fees
- Top Rated Seller: 20% discount on FVF
- Transaction fee: $0.30 per order
- International fee: 1.1% (No Store) / 1.0% (Store)
- Currency conversion: 3.3% (No Store) / 3.0% (Store)
- FVF base = sold price + shipping charged + applicable tax
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Reusable Progressive Fee Calculation
# =============================================================================

@dataclass
class FeeTier:
    """Cumulative threshold tier."""
    max_amount: Optional[float]  # None = unlimited
    rate: float


def calculate_progressive_fee(
    amount: Decimal,
    tiers: List[FeeTier],
) -> Decimal:
    """
    Progressive portion-based fee.

    Example:
        tiers = [FeeTier(4000, 0.134), FeeTier(None, 0.025)]
        amount = $5,000
        → $4,000 × 13.4% = $536
        → $1,000 × 2.5%  = $25
        → Total = $561
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
# AU Store Types
# =============================================================================

AU_STORE_NO = "no_store"
AU_STORE_BASIC = "basic"
AU_STORE_FEATURED = "featured"
AU_STORE_ANCHOR = "anchor"

AU_STORE_TYPES = {AU_STORE_NO, AU_STORE_BASIC, AU_STORE_FEATURED, AU_STORE_ANCHOR}


def is_store_seller(store_type: str) -> bool:
    return store_type in (AU_STORE_BASIC, AU_STORE_FEATURED, AU_STORE_ANCHOR)


# =============================================================================
# Category → Rate Group Mapping
# =============================================================================
# Rate groups abstract the (category, subcategory) → rate mapping.
# Each rate group has a rate per store type.

# Rate group identifiers
RG_GENERAL = "general"
RG_NFT = "nft"
RG_HOME_APPLIANCES = "home_appliances"
RG_VEHICLE_PARTS = "vehicle_parts"
RG_CAMERAS_LOWER = "cameras_lower"
RG_CAMERAS_ACCESSORIES = "cameras_accessories"
RG_CAMERAS_OTHER = "cameras_other"
RG_COMPUTERS_ACCESSORIES = "computers_accessories"
RG_COMPUTERS_HARDWARE = "computers_hardware"
RG_COMPUTERS_OTHER = "computers_other"
RG_ELECTRONICS_LOWER = "electronics_lower"
RG_ELECTRONICS_ACCESSORIES = "electronics_accessories"
RG_ELECTRONICS_OTHER = "electronics_other"
RG_HOME_ENT_LOWER = "home_ent_lower"
RG_HOME_ENT_ACCESSORIES = "home_ent_accessories"
RG_HOME_ENT_OTHER = "home_ent_other"
RG_PHONES_ACCESSORIES = "phones_accessories"
RG_PHONES_PHONES = "phones_phones"
RG_PHONES_OTHER = "phones_other"
RG_VIDEO_CONSOLES = "video_consoles"
RG_VIDEO_OTHER = "video_other"


# Categories that map directly to RG_GENERAL for Basic/Featured/Anchor
AU_GENERAL_CATEGORIES = {
    "antiques", "art", "books", "clothing", "coins",
    "collectables", "crafts", "dolls", "health_beauty",
    "jewellery", "movies", "music", "pottery",
    "sporting_goods", "stamps",
}


def resolve_rate_group(category: str, subcategory: str = "") -> str:
    """
    Map (category, subcategory) to a rate group.

    Returns the rate group identifier for fee lookup.
    """
    cat = category.lower().strip().replace(" ", "_").replace("&", "and")
    sub = subcategory.lower().strip().replace(" ", "_").replace("&", "and")

    # NFT (any category)
    if sub == "nft" or cat == "nft":
        return RG_NFT

    # Home Appliances
    if cat in ("home_appliances",):
        return RG_HOME_APPLIANCES

    # Vehicle Parts
    if cat in ("vehicle_parts", "vehicle_parts_accessories"):
        return RG_VEHICLE_PARTS

    # Cameras
    if cat in ("cameras", "cameras_camcorders"):
        if sub in ("binoculars", "camcorders", "digital_cameras",
                    "digital_photo_frames", "film_photography",
                    "vintage_movie"):
            return RG_CAMERAS_LOWER
        if sub in ("drones", "manuals", "mixed_lots", "accessories",
                    "flashes", "lenses", "lighting", "other",
                    "replacement_parts", "tripods"):
            return RG_CAMERAS_ACCESSORIES
        return RG_CAMERAS_OTHER

    # Computers
    if cat in ("computers", "computers_tablets", "computers_networking"):
        if sub in ("cables", "components", "drives", "networking",
                    "keyboards", "laptop_accessories", "manuals",
                    "mixed_lots", "monitor_mounts", "monitor_power",
                    "monitor_parts", "monitor_accessories", "other",
                    "power_protection", "printer_parts", "printer_ink",
                    "projector_parts", "software", "tablet_accessories",
                    "tablet_parts", "vintage"):
            return RG_COMPUTERS_ACCESSORIES
        if sub in ("desktops", "servers", "laptops", "monitors",
                    "printers", "projectors", "scanners", "tablets"):
            return RG_COMPUTERS_HARDWARE
        return RG_COMPUTERS_OTHER

    # Electronics
    if cat in ("electronics",):
        if sub in ("gps", "home_audio", "ipods", "pdas",
                    "cassette_players", "cd_players", "radios",
                    "smart_glasses", "torches"):
            return RG_ELECTRONICS_LOWER
        if sub in ("gps_accessories", "mixed_lots", "batteries",
                    "audio_accessories", "radio_communication",
                    "tv_accessories", "vintage"):
            return RG_ELECTRONICS_ACCESSORIES
        return RG_ELECTRONICS_OTHER

    # Home Entertainment
    if cat in ("home_entertainment", "tv_video_audio"):
        if sub in ("set_top_boxes", "dvd_players", "dvrs",
                    "home_theatre", "media_streamers", "projectors",
                    "satellite", "tvs", "vcrs"):
            return RG_HOME_ENT_LOWER
        if sub in ("projector_screens", "tv_accessories"):
            return RG_HOME_ENT_ACCESSORIES
        return RG_HOME_ENT_OTHER

    # Phones
    if cat in ("phones", "mobile_phones"):
        if sub in ("answering_machines", "batteries", "caller_id",
                    "dummy_phones", "headsets", "mixed_lots",
                    "accessories", "parts", "pagers", "pda_accessories",
                    "sim_cards", "smartwatch_accessories"):
            return RG_PHONES_ACCESSORIES
        if sub in ("corded", "cordless", "mobile_phones",
                    "smart_watches", "vintage_home", "vintage_mobile"):
            return RG_PHONES_PHONES
        return RG_PHONES_OTHER

    # Video Games
    if cat in ("video_games", "pc_video_games"):
        if sub in ("consoles",):
            return RG_VIDEO_CONSOLES
        return RG_VIDEO_OTHER

    # General categories
    if cat in AU_GENERAL_CATEGORIES:
        return RG_GENERAL

    # Fallback
    return RG_GENERAL


# =============================================================================
# Rate Tables: (store_type, rate_group) → first-$4000 rate
# =============================================================================
# All rates above $4,000 are 2.5% for all store types and groups.

ABOVE_THRESHOLD_RATE = 0.025
ABOVE_THRESHOLD = 4000.0

# First $4,000 rates by (store_type, rate_group)
AU_FIRST_BRACKET_RATES: Dict[Tuple[str, str], float] = {
    # --- No Store ---
    (AU_STORE_NO, RG_GENERAL): 0.134,
    (AU_STORE_NO, RG_NFT): 0.055,
    (AU_STORE_NO, RG_HOME_APPLIANCES): 0.134,
    (AU_STORE_NO, RG_VEHICLE_PARTS): 0.134,
    (AU_STORE_NO, RG_CAMERAS_LOWER): 0.134,
    (AU_STORE_NO, RG_CAMERAS_ACCESSORIES): 0.134,
    (AU_STORE_NO, RG_CAMERAS_OTHER): 0.134,
    (AU_STORE_NO, RG_COMPUTERS_ACCESSORIES): 0.134,
    (AU_STORE_NO, RG_COMPUTERS_HARDWARE): 0.134,
    (AU_STORE_NO, RG_COMPUTERS_OTHER): 0.134,
    (AU_STORE_NO, RG_ELECTRONICS_LOWER): 0.134,
    (AU_STORE_NO, RG_ELECTRONICS_ACCESSORIES): 0.134,
    (AU_STORE_NO, RG_ELECTRONICS_OTHER): 0.134,
    (AU_STORE_NO, RG_HOME_ENT_LOWER): 0.134,
    (AU_STORE_NO, RG_HOME_ENT_ACCESSORIES): 0.134,
    (AU_STORE_NO, RG_HOME_ENT_OTHER): 0.134,
    (AU_STORE_NO, RG_PHONES_ACCESSORIES): 0.134,
    (AU_STORE_NO, RG_PHONES_PHONES): 0.134,
    (AU_STORE_NO, RG_PHONES_OTHER): 0.134,
    (AU_STORE_NO, RG_VIDEO_CONSOLES): 0.134,
    (AU_STORE_NO, RG_VIDEO_OTHER): 0.134,

    # --- Basic Store ---
    (AU_STORE_BASIC, RG_GENERAL): 0.119,
    (AU_STORE_BASIC, RG_NFT): 0.05,
    (AU_STORE_BASIC, RG_HOME_APPLIANCES): 0.073,
    (AU_STORE_BASIC, RG_VEHICLE_PARTS): 0.113,
    (AU_STORE_BASIC, RG_CAMERAS_LOWER): 0.073,
    (AU_STORE_BASIC, RG_CAMERAS_ACCESSORIES): 0.119,
    (AU_STORE_BASIC, RG_CAMERAS_OTHER): 0.104,
    (AU_STORE_BASIC, RG_COMPUTERS_ACCESSORIES): 0.119,
    (AU_STORE_BASIC, RG_COMPUTERS_HARDWARE): 0.073,
    (AU_STORE_BASIC, RG_COMPUTERS_OTHER): 0.104,
    (AU_STORE_BASIC, RG_ELECTRONICS_LOWER): 0.073,
    (AU_STORE_BASIC, RG_ELECTRONICS_ACCESSORIES): 0.119,
    (AU_STORE_BASIC, RG_ELECTRONICS_OTHER): 0.104,
    (AU_STORE_BASIC, RG_HOME_ENT_LOWER): 0.073,
    (AU_STORE_BASIC, RG_HOME_ENT_ACCESSORIES): 0.119,
    (AU_STORE_BASIC, RG_HOME_ENT_OTHER): 0.104,
    (AU_STORE_BASIC, RG_PHONES_ACCESSORIES): 0.119,
    (AU_STORE_BASIC, RG_PHONES_PHONES): 0.073,
    (AU_STORE_BASIC, RG_PHONES_OTHER): 0.104,
    (AU_STORE_BASIC, RG_VIDEO_CONSOLES): 0.073,
    (AU_STORE_BASIC, RG_VIDEO_OTHER): 0.119,

    # --- Featured Store ---
    (AU_STORE_FEATURED, RG_GENERAL): 0.107,
    (AU_STORE_FEATURED, RG_NFT): 0.05,
    (AU_STORE_FEATURED, RG_HOME_APPLIANCES): 0.066,
    (AU_STORE_FEATURED, RG_VEHICLE_PARTS): 0.102,
    (AU_STORE_FEATURED, RG_CAMERAS_LOWER): 0.066,
    (AU_STORE_FEATURED, RG_CAMERAS_ACCESSORIES): 0.107,
    (AU_STORE_FEATURED, RG_CAMERAS_OTHER): 0.094,
    (AU_STORE_FEATURED, RG_COMPUTERS_ACCESSORIES): 0.107,
    (AU_STORE_FEATURED, RG_COMPUTERS_HARDWARE): 0.066,
    (AU_STORE_FEATURED, RG_COMPUTERS_OTHER): 0.094,
    (AU_STORE_FEATURED, RG_ELECTRONICS_LOWER): 0.066,
    (AU_STORE_FEATURED, RG_ELECTRONICS_ACCESSORIES): 0.107,
    (AU_STORE_FEATURED, RG_ELECTRONICS_OTHER): 0.094,
    (AU_STORE_FEATURED, RG_HOME_ENT_LOWER): 0.066,
    (AU_STORE_FEATURED, RG_HOME_ENT_ACCESSORIES): 0.107,
    (AU_STORE_FEATURED, RG_HOME_ENT_OTHER): 0.094,
    (AU_STORE_FEATURED, RG_PHONES_ACCESSORIES): 0.107,
    (AU_STORE_FEATURED, RG_PHONES_PHONES): 0.066,
    (AU_STORE_FEATURED, RG_PHONES_OTHER): 0.094,
    (AU_STORE_FEATURED, RG_VIDEO_CONSOLES): 0.066,
    (AU_STORE_FEATURED, RG_VIDEO_OTHER): 0.107,

    # --- Anchor Store ---
    (AU_STORE_ANCHOR, RG_GENERAL): 0.101,
    (AU_STORE_ANCHOR, RG_NFT): 0.05,
    (AU_STORE_ANCHOR, RG_HOME_APPLIANCES): 0.062,
    (AU_STORE_ANCHOR, RG_VEHICLE_PARTS): 0.096,
    (AU_STORE_ANCHOR, RG_CAMERAS_LOWER): 0.062,
    (AU_STORE_ANCHOR, RG_CAMERAS_ACCESSORIES): 0.101,
    (AU_STORE_ANCHOR, RG_CAMERAS_OTHER): 0.088,
    (AU_STORE_ANCHOR, RG_COMPUTERS_ACCESSORIES): 0.101,
    (AU_STORE_ANCHOR, RG_COMPUTERS_HARDWARE): 0.062,
    (AU_STORE_ANCHOR, RG_COMPUTERS_OTHER): 0.088,
    (AU_STORE_ANCHOR, RG_ELECTRONICS_LOWER): 0.062,
    (AU_STORE_ANCHOR, RG_ELECTRONICS_ACCESSORIES): 0.101,
    (AU_STORE_ANCHOR, RG_ELECTRONICS_OTHER): 0.088,
    (AU_STORE_ANCHOR, RG_HOME_ENT_LOWER): 0.062,
    (AU_STORE_ANCHOR, RG_HOME_ENT_ACCESSORIES): 0.101,
    (AU_STORE_ANCHOR, RG_HOME_ENT_OTHER): 0.088,
    (AU_STORE_ANCHOR, RG_PHONES_ACCESSORIES): 0.101,
    (AU_STORE_ANCHOR, RG_PHONES_PHONES): 0.062,
    (AU_STORE_ANCHOR, RG_PHONES_OTHER): 0.088,
    (AU_STORE_ANCHOR, RG_VIDEO_CONSOLES): 0.062,
    (AU_STORE_ANCHOR, RG_VIDEO_OTHER): 0.101,
}


def get_au_fvf_tiers(store_type: str, rate_group: str) -> List[FeeTier]:
    """Get progressive FVF tiers for a store type and rate group."""
    key = (store_type, rate_group)
    first_rate = AU_FIRST_BRACKET_RATES.get(key, 0.134)
    return [
        FeeTier(ABOVE_THRESHOLD, first_rate),
        FeeTier(None, ABOVE_THRESHOLD_RATE),
    ]


# =============================================================================
# Transaction Fee
# =============================================================================

AU_TRANSACTION_FEE_PER_ORDER = Decimal("0.30")


def calculate_au_transaction_fee(num_orders: int) -> Decimal:
    if num_orders < 1:
        return Decimal("0")
    return AU_TRANSACTION_FEE_PER_ORDER * num_orders


# =============================================================================
# Top Rated Seller Discount
# =============================================================================

AU_TOP_RATED_DISCOUNT = Decimal("0.20")  # 20% off FVF


def apply_top_rated_discount(
    fvf: Decimal, seller_level: str
) -> Decimal:
    if seller_level == "top_rated":
        return fvf * (Decimal("1") - AU_TOP_RATED_DISCOUNT)
    return fvf


# =============================================================================
# GST on eBay Fees (Store sellers without ABN)
# =============================================================================

AU_GST_RATE = Decimal("0.10")  # 10%


def apply_gst_on_fees(
    total_ebay_fees: Decimal,
    store_type: str,
    has_abn: bool,
) -> Decimal:
    """
    Apply 10% GST on eBay fees for store sellers without ABN.

    No Store fees already include GST.
    """
    if store_type == AU_STORE_NO:
        return Decimal("0")  # Already included
    if has_abn:
        return Decimal("0")  # ABN holders exempt
    return total_ebay_fees * AU_GST_RATE


# =============================================================================
# International Fee
# =============================================================================

AU_INTL_RATE_NO_STORE = Decimal("0.011")   # 1.1%
AU_INTL_RATE_STORE = Decimal("0.010")      # 1.0%


def calculate_au_international_fee(
    sale_amount: Decimal,
    store_type: str,
    overseas: bool,
) -> Decimal:
    if not overseas:
        return Decimal("0")
    rate = AU_INTL_RATE_NO_STORE if store_type == AU_STORE_NO else AU_INTL_RATE_STORE
    return sale_amount * rate


# =============================================================================
# Currency Conversion Fee
# =============================================================================

AU_CURRENCY_CONV_NO_STORE = Decimal("0.033")  # 3.3%
AU_CURRENCY_CONV_STORE = Decimal("0.030")     # 3.0%


def calculate_au_currency_conversion(
    payout_amount: Decimal,
    store_type: str,
    currency_conversion: bool,
) -> Decimal:
    if not currency_conversion:
        return Decimal("0")
    rate = (
        AU_CURRENCY_CONV_NO_STORE
        if store_type == AU_STORE_NO
        else AU_CURRENCY_CONV_STORE
    )
    return payout_amount * rate


# =============================================================================
# Promoted Listings
# =============================================================================

def calculate_au_promoted_fee(
    sale_amount: Decimal,
    promoted_rate: float,
) -> Decimal:
    """
    AU promoted listing fee.

    Base: total sale amount (assumption — source not explicit).
    """
    if promoted_rate <= 0:
        return Decimal("0")
    return sale_amount * Decimal(str(promoted_rate / 100.0))


# =============================================================================
# Charity
# =============================================================================

def calculate_au_charity(
    sold_price: Decimal,
    charity_percent: float,
) -> Decimal:
    if charity_percent <= 0:
        return Decimal("0")
    return sold_price * Decimal(str(charity_percent / 100.0))