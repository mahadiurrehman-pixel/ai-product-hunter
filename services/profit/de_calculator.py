"""
Germany (DE) eBay marketplace profit calculator.

Handles DE-specific fee calculations including:
- Private / Commercial seller types
- eBay Shop threshold variations
- Category/subcategory tiered FVF
- FVF cap (structural, values not supplied)
- VAT-inclusive fees (19% already in rates)
- International fees by region
- Excluded categories (Motors, Real Estate, Classified Ads)
- No PayPal fees (Managed Payments only)
"""
from decimal import Decimal
from typing import List

from utils.logger import get_logger
from .models import (
    FeeBreakdown,
    ProfitInput,
    ProfitResult,
    DESellerType,
    DEBuyerRegion,
    TaxType,
)
from .de_fees import (
    calculate_tiered_fee,
    is_excluded_category,
    get_private_rate_key,
    DE_PRIVATE_RATES,
    get_de_commercial_tiers,
    apply_de_fvf_cap,
    calculate_de_international_fee,
    DE_FVF_CAP_CONFIGURED,
)

logger = get_logger(__name__)


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class DEProfitCalculator:
    """Germany (DE) eBay marketplace profit calculator."""

    def calculate(self, inputs: ProfitInput) -> ProfitResult:
        warnings: List[str] = []
        assumptions: List[str] = []

        # Validate inputs
        if inputs.sold_price <= 0:
            warnings.append("Sold price is zero or negative")
        if inputs.item_cost < 0:
            warnings.append("Item cost is negative")
        if inputs.num_orders < 1:
            inputs.num_orders = 1

        # Check excluded categories
        if is_excluded_category(inputs.category):
            warnings.append(
                f"Category '{inputs.category}' is excluded from "
                f"DE fee calculation (Motors/Real Estate/Classified Ads)"
            )
            return self._unsupported_result(inputs, warnings)

        seller_type = (
            inputs.de_seller_type.value
            if inputs.de_seller_type
            else "private"
        )
        buyer_region = (
            inputs.de_buyer_region.value
            if inputs.de_buyer_region
            else "eurozone_sweden"
        )
        has_shop = inputs.ebay_shop

        # Revenue
        gross_per_item = _d(inputs.sold_price) + _d(inputs.shipping_charged)

        # Sales tax (if configured by user)
        sales_tax = Decimal("0")
        if inputs.tax_type == TaxType.PERCENTAGE:
            if inputs.tax_includes_shipping:
                taxable = _d(inputs.sold_price) + _d(inputs.shipping_charged)
            else:
                taxable = _d(inputs.sold_price)
            sales_tax = taxable * Decimal(str(inputs.tax_rate / 100.0))
        elif inputs.tax_type == TaxType.FIXED:
            sales_tax = _d(inputs.tax_fixed_amount)

        # FVF calculation
        fvf_base = _d(inputs.sold_price) + _d(inputs.shipping_charged)

        if seller_type == "private":
            rate_key = get_private_rate_key(buyer_region)
            tiers = DE_PRIVATE_RATES[rate_key]["tiers"]
            variable_fvf = calculate_tiered_fee(fvf_base, tiers)
            effective_rate = tiers[0].rate if tiers else 0.0
        else:
            tiers = get_de_commercial_tiers(
                inputs.category, inputs.subcategory, has_shop
            )
            variable_fvf = calculate_tiered_fee(fvf_base, tiers)
            effective_rate = tiers[0].rate if tiers else 0.0

        # Apply FVF cap (structural)
        variable_fvf, cap_applied = apply_de_fvf_cap(
            variable_fvf, inputs.category, seller_type, has_shop
        )

        fvf_per_item = variable_fvf / inputs.num_orders

        # No separate transaction fee for DE (not in source)
        transaction_per_item = Decimal("0")

        # International fee
        intl_fee = calculate_de_international_fee(
            fvf_base, seller_type, buyer_region, inputs.overseas_sales
        )

        # Promoted listings (user-configured, not DE-specific)
        promoted_fee = Decimal("0")
        if inputs.promoted_rate > 0:
            promoted_fee = _d(inputs.sold_price) * Decimal(
                str(inputs.promoted_rate / 100.0)
            )

        # Charity (user-configured)
        charity = Decimal("0")
        if inputs.charity_percent > 0:
            charity = _d(inputs.sold_price) * Decimal(
                str(inputs.charity_percent / 100.0)
            )

        # Total fees per item (VAT already included in FVF rates)
        total_fees_per_item = fvf_per_item + intl_fee + promoted_fee

        # Total costs per item
        total_costs_per_item = (
            _d(inputs.item_cost)
            + _d(inputs.shipping_cost)
            + total_fees_per_item
            + charity
            + _d(inputs.other_costs)
        )

        # Profit
        net_profit_per_item = gross_per_item - total_costs_per_item
        total_revenue = gross_per_item * inputs.num_orders
        total_costs = total_costs_per_item * inputs.num_orders
        total_profit = net_profit_per_item * inputs.num_orders

        # Margin and ROI
        profit_margin = (
            float(net_profit_per_item / gross_per_item * 100)
            if gross_per_item > 0 else 0.0
        )
        investment = _d(inputs.item_cost) + _d(inputs.shipping_cost)
        roi = (
            float(net_profit_per_item / investment * 100)
            if investment > 0 else 0.0
        )

        # Effective percentages
        fvf_pct = self._pct(fvf_per_item, gross_per_item)
        intl_pct = self._pct(intl_fee, gross_per_item)
        promoted_pct = self._pct(promoted_fee, gross_per_item)
        charity_pct = self._pct(charity, gross_per_item)
        total_fees_pct = self._pct(total_fees_per_item, gross_per_item)

        # Assumptions
        assumptions.append("All eBay fees include 19% VAT (VAT-inclusive)")
        assumptions.append("Managed Payments (PayPal fees obsolete)")
        if seller_type == "private":
            assumptions.append(
                f"Private seller FVF: {effective_rate * 100:.1f}% "
                f"(region: {buyer_region})"
            )
        else:
            shop_str = "with Shop" if has_shop else "without Shop"
            assumptions.append(
                f"Commercial FVF: {effective_rate * 100:.1f}% "
                f"({shop_str}, {inputs.category})"
            )
        if inputs.overseas_sales:
            assumptions.append(
                f"International fee: {buyer_region}"
            )
        if not DE_FVF_CAP_CONFIGURED:
            assumptions.append(
                "FVF cap: structurally supported but exact values "
                "not configured"
            )

        # Warnings
        if inputs.item_cost <= 0:
            warnings.append("Item cost is zero — profit may be inflated")
        if roi > 500:
            warnings.append("ROI exceeds 500% — verify data")
        if net_profit_per_item < 0:
            warnings.append("Negative profit — this sale loses money")
        if not DE_FVF_CAP_CONFIGURED:
            warnings.append(
                "Germany FVF cap rules are supported structurally, "
                "but exact cap value is not configured"
            )

        return ProfitResult(
            marketplace="DE",
            currency="EUR",
            sold_price=_d(inputs.sold_price),
            shipping_charged=_d(inputs.shipping_charged),
            item_cost=_d(inputs.item_cost),
            shipping_cost=_d(inputs.shipping_cost),
            num_orders=inputs.num_orders,
            store_type=seller_type,
            seller_level=inputs.seller_level.value,
            overseas_sales=inputs.overseas_sales,
            category=inputs.category,
            subcategory=inputs.subcategory,
            gross_revenue_per_item=gross_per_item,
            total_revenue=total_revenue,
            total_item_cost=_d(inputs.item_cost) * inputs.num_orders,
            total_shipping_cost=_d(inputs.shipping_cost) * inputs.num_orders,
            fees=FeeBreakdown(
                fvf=fvf_per_item,
                variable_fvf=fvf_per_item,
                fvf_effective_rate=effective_rate,
                transaction_fee=transaction_per_item,
                promoted_fee=promoted_fee,
                international_fee=intl_fee,
                charity_cost=charity,
                sales_tax=sales_tax,
                vat_on_fees=Decimal("0"),  # VAT already in FVF
                total_fees=total_fees_per_item,
                fvf_pct=fvf_pct,
                transaction_pct=0.0,
                promoted_pct=promoted_pct,
                international_pct=intl_pct,
                charity_pct=charity_pct,
                vat_pct=0.0,
                total_fees_pct=total_fees_pct,
            ),
            total_costs=total_costs,
            net_profit_per_item=net_profit_per_item,
            total_profit=total_profit,
            profit_margin=round(profit_margin, 2),
            roi=round(roi, 2),
            is_profitable=net_profit_per_item > 0,
            profit_min=net_profit_per_item,
            profit_max=net_profit_per_item,
            margin_min=profit_margin,
            margin_max=profit_margin,
            confidence="high" if inputs.item_cost > 0 else "low",
            assumptions=assumptions,
            warnings=warnings,
        )

    def _unsupported_result(
        self, inputs: ProfitInput, warnings: List[str]
    ) -> ProfitResult:
        """Return a result for unsupported categories."""
        return ProfitResult(
            marketplace="DE",
            currency="EUR",
            sold_price=_d(inputs.sold_price),
            item_cost=_d(inputs.item_cost),
            category=inputs.category,
            confidence="low",
            assumptions=["Category not supported for DE fee calculation"],
            warnings=warnings,
        )

    def _pct(self, amount: Decimal, base: Decimal) -> float:
        if base <= 0:
            return 0.0
        return round(float(amount / base * 100), 2)