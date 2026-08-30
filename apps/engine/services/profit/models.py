"""
Profit calculation data models.

Supports US, UK, DE, and AU marketplace profit calculations.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional


class StoreType(str, Enum):
    """US eBay store types."""
    NO_STORE = "no_store"
    STARTER = "starter"
    BASIC = "basic"
    PREMIUM = "premium"
    ANCHOR = "anchor"
    ENTERPRISE = "enterprise"


class UKSellerType(str, Enum):
    """UK eBay seller types."""
    PRIVATE = "private"
    BUSINESS = "business"


class DESellerType(str, Enum):
    """Germany eBay seller types."""
    PRIVATE = "private"
    COMMERCIAL = "commercial"


class AUStoreType(str, Enum):
    """Australia eBay store types."""
    NO_STORE = "no_store"
    BASIC = "basic"
    FEATURED = "featured"
    ANCHOR = "anchor"

class CAStoreType(str, Enum):
    """Canada eBay store types."""
    NO_STORE = "no_store"
    BASIC = "basic"
    PREMIUM = "premium"
    ANCHOR = "anchor"


class CADestination(str, Enum):
    """Canada international destination."""
    DOMESTIC = "domestic"
    US = "us"
    OTHER_INTERNATIONAL = "other_international"

class SellerLevel(str, Enum):
    TOP_RATED = "top_rated"
    ABOVE_STANDARD = "above_standard"
    BELOW_STANDARD = "below_standard"


class TaxType(str, Enum):
    PERCENTAGE = "percentage"
    FIXED = "fixed"
    NONE = "none"


class UKBuyerRegion(str, Enum):
    """UK international buyer regions."""
    DOMESTIC = "domestic"
    EUROZONE_NORTHERN_EUROPE = "eurozone_northern_europe"
    US_CANADA = "us_canada"
    OTHER = "other"


class DEBuyerRegion(str, Enum):
    """Germany international buyer regions."""
    EUROZONE_SWEDEN = "eurozone_sweden"
    EUROPE_USA_CANADA = "europe_usa_canada"
    UK = "uk"
    OTHER = "other"


@dataclass
class ProfitInput:
    """Input parameters for profit calculation."""

    marketplace: str = "US"
    currency: str = "USD"

    # Revenue
    sold_price: Decimal = Decimal("0")
    shipping_charged: Decimal = Decimal("0")

    # Costs
    item_cost: Decimal = Decimal("0")
    shipping_cost: Decimal = Decimal("0")
    other_costs: Decimal = Decimal("0")

    # Orders
    num_orders: int = 1

    # US seller configuration
    store_type: StoreType = StoreType.NO_STORE
    seller_level: SellerLevel = SellerLevel.ABOVE_STANDARD
    overseas_sales: bool = False

    # UK-specific fields
    uk_seller_type: Optional[UKSellerType] = None
    vat_registered: bool = False
    buyer_region: UKBuyerRegion = UKBuyerRegion.DOMESTIC
    subcategory: str = ""
    currency_conversion: bool = False

    # DE-specific fields
    de_seller_type: Optional[DESellerType] = None
    ebay_shop: bool = False
    de_buyer_region: DEBuyerRegion = DEBuyerRegion.EUROZONE_SWEDEN

    # AU-specific fields
    au_store_type: Optional[AUStoreType] = None
    has_abn: bool = True

    # CA-specific fields
    ca_store_type: Optional[CAStoreType] = None
    ca_destination: CADestination = CADestination.DOMESTIC

    # Fees
    promoted_rate: float = 0.0
    charity_percent: float = 0.0

    # Sales tax / VAT
    tax_type: TaxType = TaxType.NONE
    tax_rate: float = 0.0
    tax_fixed_amount: Decimal = Decimal("0")
    tax_includes_shipping: bool = False

    # Category
    category: str = "default"


@dataclass
class FeeBreakdown:
    """Detailed fee breakdown per item."""

    fvf: Decimal = Decimal("0")
    variable_fvf: Decimal = Decimal("0")
    fvf_effective_rate: float = 0.0
    transaction_fee: Decimal = Decimal("0")
    promoted_fee: Decimal = Decimal("0")
    international_fee: Decimal = Decimal("0")
    charity_cost: Decimal = Decimal("0")
    sales_tax: Decimal = Decimal("0")
    vat_on_fees: Decimal = Decimal("0")
    currency_conversion_fee: Decimal = Decimal("0")
    total_fees: Decimal = Decimal("0")

    # Effective percentages
    fvf_pct: float = 0.0
    transaction_pct: float = 0.0
    promoted_pct: float = 0.0
    international_pct: float = 0.0
    charity_pct: float = 0.0
    vat_pct: float = 0.0
    currency_conversion_pct: float = 0.0
    total_fees_pct: float = 0.0


@dataclass
class ProfitResult:
    """Complete profit calculation result."""

    marketplace: str = "US"
    currency: str = "USD"
    sold_price: Decimal = Decimal("0")
    shipping_charged: Decimal = Decimal("0")
    item_cost: Decimal = Decimal("0")
    shipping_cost: Decimal = Decimal("0")
    num_orders: int = 1
    store_type: str = "no_store"
    seller_level: str = "above_standard"
    overseas_sales: bool = False
    category: str = "default"
    subcategory: str = ""
    ebay_shop: bool = False

    # Revenue
    gross_revenue_per_item: Decimal = Decimal("0")
    total_revenue: Decimal = Decimal("0")

    # Costs
    total_item_cost: Decimal = Decimal("0")
    total_shipping_cost: Decimal = Decimal("0")
    total_other_costs: Decimal = Decimal("0")

    # Fees
    fees: FeeBreakdown = field(default_factory=FeeBreakdown)
    total_costs: Decimal = Decimal("0")

    # Profit
    net_profit_per_item: Decimal = Decimal("0")
    total_profit: Decimal = Decimal("0")
    profit_margin: float = 0.0
    roi: float = 0.0
    is_profitable: bool = False

    # Range
    profit_min: Decimal = Decimal("0")
    profit_max: Decimal = Decimal("0")
    margin_min: float = 0.0
    margin_max: float = 0.0

    # Metadata
    confidence: str = "medium"
    assumptions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "marketplace": self.marketplace,
            "currency": self.currency,
            "sold_price": float(self.sold_price),
            "shipping_charged": float(self.shipping_charged),
            "item_cost": float(self.item_cost),
            "shipping_cost": float(self.shipping_cost),
            "num_orders": self.num_orders,
            "store_type": self.store_type,
            "seller_level": self.seller_level,
            "overseas_sales": self.overseas_sales,
            "category": self.category,
            "subcategory": self.subcategory,
            "ebay_shop": self.ebay_shop,
            "gross_revenue_per_item": float(self.gross_revenue_per_item),
            "total_revenue": float(self.total_revenue),
            "total_item_cost": float(self.total_item_cost),
            "total_shipping_cost": float(self.total_shipping_cost),
            "fees": {
                "fvf": float(self.fees.fvf),
                "variable_fvf": float(self.fees.variable_fvf),
                "fvf_effective_rate": self.fees.fvf_effective_rate,
                "fvf_pct": self.fees.fvf_pct,
                "transaction_fee": float(self.fees.transaction_fee),
                "transaction_pct": self.fees.transaction_pct,
                "promoted_fee": float(self.fees.promoted_fee),
                "promoted_pct": self.fees.promoted_pct,
                "international_fee": float(self.fees.international_fee),
                "international_pct": self.fees.international_pct,
                "charity_cost": float(self.fees.charity_cost),
                "charity_pct": self.fees.charity_pct,
                "sales_tax": float(self.fees.sales_tax),
                "vat_on_fees": float(self.fees.vat_on_fees),
                "currency_conversion_fee": float(
                    self.fees.currency_conversion_fee
                ),
                "currency_conversion_pct": self.fees.currency_conversion_pct,
                "total_fees": float(self.fees.total_fees),
                "total_fees_pct": self.fees.total_fees_pct,
            },
            "total_costs": float(self.total_costs),
            "net_profit_per_item": float(self.net_profit_per_item),
            "total_profit": float(self.total_profit),
            "profit_margin": self.profit_margin,
            "roi": self.roi,
            "is_profitable": self.is_profitable,
            "profit_range": {
                "min": float(self.profit_min),
                "max": float(self.profit_max),
                "margin_min": self.margin_min,
                "margin_max": self.margin_max,
            },
            "confidence": self.confidence,
            "assumptions": self.assumptions,
            "warnings": self.warnings,
        }