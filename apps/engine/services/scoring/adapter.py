"""
Match to Profit Adapter.

Converts a ProductMatchResult (from Phase 5) and associated marketplace
parameters into a valid ProfitInput model (for Phase 6 ProfitCalculator).
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from services.marketplace import Marketplace, validate_marketplace
from services.profit.models import (
    AUStoreType,
    CADestination,
    CAStoreType,
    DEBuyerRegion,
    DESellerType,
    ProfitInput,
    SellerLevel,
    StoreType,
    TaxType,
    UKBuyerRegion,
    UKSellerType,
)
from utils.logger import get_logger

if TYPE_CHECKING:
    from services.matching.matcher import ProductMatchResult

logger = get_logger(__name__)

# Canonical currency map per marketplace
_MARKETPLACE_CURRENCIES: Dict[Marketplace, str] = {
    Marketplace.US: "USD",
    Marketplace.UK: "GBP",
    Marketplace.DE: "EUR",
    Marketplace.AU: "AUD",
    Marketplace.CA: "CAD",
}


def _to_decimal(val: Any) -> Decimal:
    """Safely convert any numeric / string value to Decimal."""
    if val is None:
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal("0")


class MatchToProfitAdapter:
    """
    Adapter converting ProductMatchResult into a structured ProfitInput.

    Extracts price, category, and identity context from the match result
    and applies marketplace-specific configuration defaults.
    """

    def convert(
        self,
        match_result: ProductMatchResult,
        marketplace: Union[str, Marketplace] = Marketplace.US,
        ebay_listing: Optional[Dict[str, Any]] = None,
        ali_product: Optional[Any] = None,
        shipping_cost: Union[Decimal, float, str] = Decimal("0"),
        shipping_charged: Union[Decimal, float, str] = Decimal("0"),
        num_orders: int = 1,
        promoted_rate: float = 0.0,
        charity_percent: float = 0.0,
        other_costs: Union[Decimal, float, str] = Decimal("0"),
        overseas_sales: bool = False,
        # Marketplace-specific overrides
        store_type: Optional[StoreType] = None,
        seller_level: SellerLevel = SellerLevel.ABOVE_STANDARD,
        uk_seller_type: UKSellerType = UKSellerType.BUSINESS,
        de_seller_type: DESellerType = DESellerType.COMMERCIAL,
        au_store_type: AUStoreType = AUStoreType.NO_STORE,
        ca_store_type: CAStoreType = CAStoreType.NO_STORE,
        ebay_shop: bool = False,
        has_abn: bool = True,
        vat_registered: bool = False,
        currency_conversion: bool = False,
        uk_buyer_region: UKBuyerRegion = UKBuyerRegion.DOMESTIC,
        de_buyer_region: DEBuyerRegion = DEBuyerRegion.EUROZONE_SWEDEN,
        ca_destination: CADestination = CADestination.DOMESTIC,
        tax_type: TaxType = TaxType.NONE,
        tax_rate: float = 0.0,
    ) -> ProfitInput:
        """
        Convert a ProductMatchResult into a ProfitInput model.

        Args:
            match_result: Pairwise match result from ProductMatcher
            marketplace: Target marketplace ("US", "UK", "DE", "AU", "CA" or Marketplace enum)
            ebay_listing: Optional raw parsed eBay listing dictionary
            ali_product: Optional AliExpressProduct instance or dictionary
            shipping_cost: Estimated outbound supplier shipping cost
            shipping_charged: Shipping charged to the eBay buyer
            num_orders: Number of order units
            promoted_rate: Promoted ad rate percentage (e.g., 5.0 for 5%)
            charity_percent: Charity donation percentage
            other_costs: Any miscellaneous per-unit overhead
            overseas_sales: True if sold cross-border
            ... (marketplace specific configuration options)

        Returns:
            Validated ProfitInput instance
        """
        canon_mp = validate_marketplace(marketplace)
        currency = _MARKETPLACE_CURRENCIES.get(canon_mp, "USD")

        # 1. Extract sold price (eBay side)
        sold_price = self._extract_ebay_price(match_result, ebay_listing)

        # 2. Extract item sourcing cost (AliExpress side)
        item_cost = self._extract_ali_cost(match_result, ali_product)

        # 3. Extract category & subcategory from identities
        category, subcategory = self._extract_categories(match_result, ebay_listing)

        # 4. Resolve US store type fallback
        resolved_us_store = store_type if store_type is not None else StoreType.NO_STORE

        return ProfitInput(
            marketplace=canon_mp.value,
            currency=currency,
            sold_price=sold_price,
            shipping_charged=_to_decimal(shipping_charged),
            item_cost=item_cost,
            shipping_cost=_to_decimal(shipping_cost),
            other_costs=_to_decimal(other_costs),
            num_orders=max(1, num_orders),
            category=category,
            subcategory=subcategory,
            store_type=resolved_us_store,
            seller_level=seller_level,
            overseas_sales=overseas_sales,
            promoted_rate=promoted_rate,
            charity_percent=charity_percent,
            # UK specific
            uk_seller_type=uk_seller_type,
            vat_registered=vat_registered,
            buyer_region=uk_buyer_region,
            currency_conversion=currency_conversion,
            # DE specific
            de_seller_type=de_seller_type,
            ebay_shop=ebay_shop,
            de_buyer_region=de_buyer_region,
            # AU specific
            au_store_type=au_store_type,
            has_abn=has_abn,
            # CA specific
            ca_store_type=ca_store_type,
            ca_destination=ca_destination,
            # Taxes
            tax_type=tax_type,
            tax_rate=tax_rate,
        )

    def _extract_ebay_price(
        self,
        match: Optional[ProductMatchResult],
        listing_dict: Optional[Dict[str, Any]] = None,
    ) -> Decimal:
        """Extract eBay selling price from listing metadata or identity."""
        if listing_dict:
            val = listing_dict.get("price_value") or listing_dict.get("price")
            if val is not None:
                return _to_decimal(val)

        # Check eBay identity attributes / metadata
        if match and getattr(match, "ebay_identity", None):
            if hasattr(match.ebay_identity, "price_value") and match.ebay_identity.price_value:
                return _to_decimal(match.ebay_identity.price_value)

        return Decimal("0")

    def _extract_ali_cost(
        self,
        match: Optional[ProductMatchResult],
        ali_product: Optional[Any] = None,
    ) -> Decimal:
        """Extract AliExpress item cost from product object, dict, or identity."""
        if ali_product:
            if hasattr(ali_product, "price"):
                price_attr = ali_product.price
                if hasattr(price_attr, "value"):
                    return _to_decimal(price_attr.value)
                return _to_decimal(price_attr)
            if isinstance(ali_product, dict):
                val = ali_product.get("price_value") or ali_product.get("price")
                if val is not None:
                    return _to_decimal(val)

        # Check AliExpress identity metadata
        if match and getattr(match, "ali_identity", None):
            if hasattr(match.ali_identity, "price_value") and match.ali_identity.price_value:
                return _to_decimal(match.ali_identity.price_value)

        return Decimal("0")

    def _extract_categories(
        self,
        match: Optional[ProductMatchResult],
        listing_dict: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str]:
        """Extract category and subcategory strings."""
        cat = "default"
        sub = ""

        if match and getattr(match, "ebay_identity", None):
            if match.ebay_identity.product_type:
                cat = match.ebay_identity.product_type
            if getattr(match.ebay_identity, "model_family", None):
                sub = match.ebay_identity.model_family

        if cat == "default" and listing_dict:
            cat = listing_dict.get("category", "default")
            sub = listing_dict.get("subcategory", "")

        return cat, sub