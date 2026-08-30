"""
UK eBay marketplace profit calculator.

Handles UK-specific fee calculations including:
- Private/Business seller types
- Category/subcategory FVF with tiered brackets
- FVF cap (£250)
- Top Rated discount (variable FVF only)
- VAT on eBay fees (business, VAT-registered)
- International fees by region
- Currency conversion (2.5%)
- Promoted listings (excludes postage)
- Charity (excludes shipping)
"""
from decimal import Decimal
from typing import List

from utils.logger import get_logger
from .models import (
    FeeBreakdown,
    ProfitInput,
    ProfitResult,
    UKSellerType,
    UKBuyerRegion,
    TaxType,
)
from .uk_fees import (
    calculate_uk_fvf,
    calculate_uk_international_fee,
    calculate_uk_promoted_fee,
    calculate_uk_charity,
    calculate_uk_vat_on_fees,
    calculate_uk_currency_conversion,
)

logger = get_logger(__name__)


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class UKProfitCalculator:
    """UK eBay marketplace profit calculator."""

    def calculate(self, inputs: ProfitInput) -> ProfitResult:
        warnings: List[str] = []
        assumptions: List[str] = []

        if inputs.sold_price <= 0:
            warnings.append("Sold price is zero or negative")
        if inputs.item_cost < 0:
            warnings.append("Item cost is negative")
        if inputs.num_orders < 1:
            inputs.num_orders = 1

        seller_type = (
            inputs.uk_seller_type.value
            if inputs.uk_seller_type
            else "private"
        )
        buyer_region = (
            inputs.buyer_region.value
            if inputs.buyer_region
            else "domestic"
        )

        # Revenue
        gross_per_item = _d(inputs.sold_price) + _d(inputs.shipping_charged)

        # Sales tax / VAT on sale
        sales_tax = Decimal("0")
        if inputs.tax_type == TaxType.PERCENTAGE:
            if inputs.tax_includes_shipping:
                taxable = _d(inputs.sold_price) + _d(inputs.shipping_charged)
            else:
                taxable = _d(inputs.sold_price)
            sales_tax = taxable * Decimal(str(inputs.tax_rate / 100.0))
        elif inputs.tax_type == TaxType.FIXED:
            sales_tax = _d(inputs.tax_fixed_amount)

        # FVF
        total_fvf, variable_fvf, effective_rate = calculate_uk_fvf(
            sale_amount=_d(inputs.sold_price) + _d(inputs.shipping_charged),
            seller_type=seller_type,
            category=inputs.category,
            subcategory=inputs.subcategory,
            seller_level=inputs.seller_level.value,
            num_orders=inputs.num_orders,
        )
        fvf_per_item = total_fvf / inputs.num_orders
        variable_per_item = variable_fvf / inputs.num_orders

        # Transaction fee (already included in FVF, extract for reporting)
        per_order = Decimal("0.30")
        if (
            seller_type == "business"
            and _d(inputs.sold_price) <= Decimal("10")
        ):
            per_order = Decimal("0.10")
        transaction_per_item = per_order

        # Promoted listings (excludes postage)
        promoted_fee = calculate_uk_promoted_fee(
            _d(inputs.sold_price), inputs.promoted_rate
        )

        # International fee
        intl_fee = calculate_uk_international_fee(
            _d(inputs.sold_price) + _d(inputs.shipping_charged),
            seller_type,
            buyer_region,
            inputs.overseas_sales,
        )

        # Charity (excludes shipping)
        charity = calculate_uk_charity(
            _d(inputs.sold_price), inputs.charity_percent
        )

        # VAT on eBay fees (business, VAT-registered)
        total_ebay_fees_before_vat = fvf_per_item + promoted_fee + intl_fee
        vat_on_fees = calculate_uk_vat_on_fees(
            total_ebay_fees_before_vat,
            inputs.vat_registered,
            seller_type,
        )

        # Currency conversion
        total_payout = gross_per_item - fvf_per_item
        currency_fee = calculate_uk_currency_conversion(
            total_payout, inputs.currency_conversion
        )

        # Total fees
        total_fees_per_item = (
            fvf_per_item + promoted_fee + intl_fee + vat_on_fees + currency_fee
        )

        # Total costs
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
        transaction_pct = self._pct(transaction_per_item, gross_per_item)
        promoted_pct = self._pct(promoted_fee, gross_per_item)
        intl_pct = self._pct(intl_fee, gross_per_item)
        charity_pct = self._pct(charity, gross_per_item)
        vat_pct = self._pct(vat_on_fees, gross_per_item)
        currency_pct = self._pct(currency_fee, gross_per_item)
        total_fees_pct = self._pct(total_fees_per_item, gross_per_item)

        # Assumptions
        assumptions.append(f"UK FVF: {effective_rate * 100:.2f}%")
        if inputs.promoted_rate > 0:
            assumptions.append(
                f"Promoted: {inputs.promoted_rate}% (excl. postage)"
            )
        if inputs.charity_percent > 0:
            assumptions.append(
                f"Charity: {inputs.charity_percent}% (excl. shipping)"
            )
        if inputs.overseas_sales:
            assumptions.append(f"International: {buyer_region}")
        if inputs.vat_registered and seller_type == "business":
            assumptions.append("VAT: 20% on eBay fees")
        if inputs.currency_conversion:
            assumptions.append("Currency conversion: 2.5%")

        # Warnings
        if inputs.item_cost <= 0:
            warnings.append("Item cost is zero")
        if roi > 500:
            warnings.append("ROI exceeds 500% — verify data")
        if net_profit_per_item < 0:
            warnings.append("Negative profit")
        if inputs.currency_conversion:
            warnings.append(
                "Currency conversion fee applied — verify if applicable"
            )

        return ProfitResult(
            marketplace="UK",
            currency="GBP",
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
                variable_fvf=variable_per_item,
                fvf_effective_rate=effective_rate,
                transaction_fee=transaction_per_item,
                promoted_fee=promoted_fee,
                international_fee=intl_fee,
                charity_cost=charity,
                sales_tax=sales_tax,
                vat_on_fees=vat_on_fees,
                currency_conversion_fee=currency_fee,
                total_fees=total_fees_per_item,
                fvf_pct=fvf_pct,
                transaction_pct=transaction_pct,
                promoted_pct=promoted_pct,
                international_pct=intl_pct,
                charity_pct=charity_pct,
                vat_pct=vat_pct,
                currency_conversion_pct=currency_pct,
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

    def _pct(self, amount: Decimal, base: Decimal) -> float:
        if base <= 0:
            return 0.0
        return round(float(amount / base * 100), 2)