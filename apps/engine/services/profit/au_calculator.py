"""
Australia (AU) eBay marketplace profit calculator.

Handles AU-specific fee calculations including:
- No Store / Basic / Featured / Anchor store types
- Progressive $4,000 threshold with category-specific rates
- GST: included for No Store, +10% for store sellers without ABN
- Top Rated Seller 20% FVF discount
- Transaction fee $0.30 per order
- International fee 1.1% / 1.0%
- Currency conversion 3.3% / 3.0%
- FVF base = sold price + shipping + tax
"""
from decimal import Decimal
from typing import List

from utils.logger import get_logger
from .models import (
    FeeBreakdown,
    ProfitInput,
    ProfitResult,
    AUStoreType,
    TaxType,
)
from .au_fees import (
    AU_STORE_NO,
    calculate_progressive_fee,
    resolve_rate_group,
    get_au_fvf_tiers,
    calculate_au_transaction_fee,
    apply_top_rated_discount,
    apply_gst_on_fees,
    calculate_au_international_fee,
    calculate_au_currency_conversion,
    calculate_au_promoted_fee,
    calculate_au_charity,
    is_store_seller,
)

logger = get_logger(__name__)


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class AUProfitCalculator:
    """Australia (AU) eBay marketplace profit calculator."""

    def calculate(self, inputs: ProfitInput) -> ProfitResult:
        warnings: List[str] = []
        assumptions: List[str] = []

        # --- Validation ---
        if inputs.sold_price <= 0:
            warnings.append("Sold price is zero or negative")
        if inputs.item_cost < 0:
            warnings.append("Item cost is negative")
        if inputs.shipping_cost < 0:
            warnings.append("Shipping cost is negative")
        if inputs.num_orders < 1:
            warnings.append("Number of orders must be at least 1")
            inputs.num_orders = 1
        if inputs.currency and inputs.currency.upper() != "AUD":
            warnings.append(
                f"Currency '{inputs.currency}' is not AUD — "
                f"no FX conversion available"
            )

        store_type = (
            inputs.au_store_type.value
            if inputs.au_store_type
            else AU_STORE_NO
        )
        seller_level = inputs.seller_level.value
        has_abn = inputs.has_abn

        # --- Revenue ---
        gross_per_item = _d(inputs.sold_price) + _d(inputs.shipping_charged)

        # --- Sales Tax ---
        sales_tax = Decimal("0")
        if inputs.tax_type == TaxType.PERCENTAGE:
            if inputs.tax_includes_shipping:
                taxable = _d(inputs.sold_price) + _d(inputs.shipping_charged)
            else:
                taxable = _d(inputs.sold_price)
            sales_tax = taxable * Decimal(str(inputs.tax_rate / 100.0))
        elif inputs.tax_type == TaxType.FIXED:
            sales_tax = _d(inputs.tax_fixed_amount)

        # --- FVF Base (sold + shipping + tax) ---
        fvf_base = (
            _d(inputs.sold_price)
            + _d(inputs.shipping_charged)
            + sales_tax
        )

        # --- FVF Calculation ---
        rate_group = resolve_rate_group(inputs.category, inputs.subcategory)
        tiers = get_au_fvf_tiers(store_type, rate_group)
        base_fvf = calculate_progressive_fee(fvf_base, tiers)

        # Top Rated discount
        base_fvf = apply_top_rated_discount(base_fvf, seller_level)

        fvf_per_item = base_fvf / inputs.num_orders
        effective_rate = (
            float(fvf_per_item / fvf_base) if fvf_base > 0 else 0.0
        )

        # --- Transaction Fee ---
        total_txn = calculate_au_transaction_fee(inputs.num_orders)
        txn_per_item = total_txn / inputs.num_orders

        # --- International Fee ---
        intl_fee = calculate_au_international_fee(
            fvf_base, store_type, inputs.overseas_sales
        )

        # --- Currency Conversion ---
        payout = gross_per_item - fvf_per_item - txn_per_item
        currency_fee = calculate_au_currency_conversion(
            max(payout, Decimal("0")),
            store_type,
            inputs.currency_conversion,
        )

        # --- Promoted Listings ---
        promoted_fee = calculate_au_promoted_fee(
            fvf_base, inputs.promoted_rate
        )

        # --- Subtotal eBay fees before GST ---
        ebay_fees_before_gst = (
            fvf_per_item + txn_per_item + intl_fee
            + currency_fee + promoted_fee
        )

        # --- GST on eBay fees ---
        gst_on_fees = apply_gst_on_fees(
            ebay_fees_before_gst, store_type, has_abn
        )

        # --- Total eBay fees ---
        total_ebay_fees = ebay_fees_before_gst + gst_on_fees

        # --- Charity ---
        charity = calculate_au_charity(
            _d(inputs.sold_price), inputs.charity_percent
        )

        # --- Total costs ---
        total_costs_per_item = (
            _d(inputs.item_cost)
            + _d(inputs.shipping_cost)
            + total_ebay_fees
            + charity
            + _d(inputs.other_costs)
        )

        # --- Profit ---
        net_profit = gross_per_item - total_costs_per_item
        total_revenue = gross_per_item * inputs.num_orders
        total_costs = total_costs_per_item * inputs.num_orders
        total_profit = net_profit * inputs.num_orders

        # --- Margin & ROI ---
        margin = (
            float(net_profit / gross_per_item * 100)
            if gross_per_item > 0 else 0.0
        )
        investment = _d(inputs.item_cost) + _d(inputs.shipping_cost)
        if investment > 0:
            roi = float(net_profit / investment * 100)
        else:
            roi = 0.0
            if _d(inputs.item_cost) == 0:
                warnings.append(
                    "Item cost is zero — ROI undefined, set to 0"
                )

        if roi > 500:
            warnings.append(
                "Suspiciously high ROI exceeds 500% — verify source cost and sale price"
            )
        if net_profit < 0:
            warnings.append("Negative profit — this sale loses money")
        if net_profit == 0:
            warnings.append("Zero profit")

        # --- Effective percentages ---
        fvf_pct = self._pct(fvf_per_item, gross_per_item)
        txn_pct = self._pct(txn_per_item, gross_per_item)
        promoted_pct = self._pct(promoted_fee, gross_per_item)
        intl_pct = self._pct(intl_fee, gross_per_item)
        currency_pct = self._pct(currency_fee, gross_per_item)
        charity_pct = self._pct(charity, gross_per_item)
        total_fees_pct = self._pct(total_ebay_fees, gross_per_item)

        # --- Assumptions ---
        assumptions.append("FVF base = sold price + shipping + tax")
        assumptions.append(f"Store type: {store_type}")
        if store_type == AU_STORE_NO:
            assumptions.append("No Store fees include GST")
        elif not has_abn:
            assumptions.append(
                "Store seller without ABN: +10% GST on eBay fees"
            )
        else:
            assumptions.append("Store seller with ABN: no extra GST")
        if seller_level == "top_rated":
            assumptions.append("Top Rated: 20% FVF discount applied")
        if inputs.overseas_sales:
            rate_str = "1.1%" if store_type == AU_STORE_NO else "1.0%"
            assumptions.append(f"International fee: {rate_str}")
        if inputs.currency_conversion:
            rate_str = "3.3%" if store_type == AU_STORE_NO else "3.0%"
            assumptions.append(f"Currency conversion: {rate_str}")
        if inputs.promoted_rate > 0:
            assumptions.append(
                f"Promoted listings: {inputs.promoted_rate}% "
                f"(base: total sale amount — assumption)"
            )
        assumptions.append(f"Rate group: {rate_group}")

        return ProfitResult(
            marketplace="AU",
            currency="AUD",
            sold_price=_d(inputs.sold_price),
            shipping_charged=_d(inputs.shipping_charged),
            item_cost=_d(inputs.item_cost),
            shipping_cost=_d(inputs.shipping_cost),
            num_orders=inputs.num_orders,
            store_type=store_type,
            seller_level=seller_level,
            overseas_sales=inputs.overseas_sales,
            category=inputs.category,
            subcategory=inputs.subcategory,
            ebay_shop=is_store_seller(store_type),
            gross_revenue_per_item=gross_per_item,
            total_revenue=total_revenue,
            total_item_cost=_d(inputs.item_cost) * inputs.num_orders,
            total_shipping_cost=_d(inputs.shipping_cost) * inputs.num_orders,
            fees=FeeBreakdown(
                fvf=fvf_per_item,
                variable_fvf=fvf_per_item,
                fvf_effective_rate=effective_rate,
                transaction_fee=txn_per_item,
                promoted_fee=promoted_fee,
                international_fee=intl_fee,
                charity_cost=charity,
                sales_tax=sales_tax,
                vat_on_fees=gst_on_fees,
                currency_conversion_fee=currency_fee,
                total_fees=total_ebay_fees,
                fvf_pct=fvf_pct,
                transaction_pct=txn_pct,
                promoted_pct=promoted_pct,
                international_pct=intl_pct,
                charity_pct=charity_pct,
                vat_pct=self._pct(gst_on_fees, gross_per_item),
                currency_conversion_pct=currency_pct,
                total_fees_pct=total_fees_pct,
            ),
            total_costs=total_costs,
            net_profit_per_item=net_profit,
            total_profit=total_profit,
            profit_margin=round(margin, 2),
            roi=round(roi, 2),
            is_profitable=net_profit > 0,
            profit_min=net_profit,
            profit_max=net_profit,
            margin_min=margin,
            margin_max=margin,
            confidence="high" if _d(inputs.item_cost) > 0 else "low",
            assumptions=assumptions,
            warnings=warnings,
        )

    def _pct(self, amount: Decimal, base: Decimal) -> float:
        if base <= 0:
            return 0.0
        return round(float(amount / base * 100), 2)