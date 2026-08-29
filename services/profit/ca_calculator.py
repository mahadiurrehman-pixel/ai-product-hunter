"""
Canada (CA) eBay marketplace profit calculator.

Handles CA-specific fee calculations:
- No Store / Basic / Premium / Anchor
- Category/subcategory-specific FVF with progressive thresholds
- Seller level: Top Rated -10%, Below Average +5%
- International: Domestic 0%, US 0.4%, Other 1.0%
- FVF base includes shipping and tax (Managed Payments)
- Athletic Shoes: FVF on sold price only
- Transaction fee, promoted base, charity, currency conversion:
  NOT supplied — emitted as warnings
"""
from decimal import Decimal
from typing import List

from utils.logger import get_logger
from .models import (
    FeeBreakdown,
    ProfitInput,
    ProfitResult,
    CAStoreType,
    CADestination,
    TaxType,
)
from .ca_fees import (
    CA_STORE_NO,
    CA_DEST_DOMESTIC,
    calculate_progressive_fee,
    resolve_ca_rule,
    apply_seller_level_adjustment,
    calculate_ca_international_fee,
    is_store_seller,
)

logger = get_logger(__name__)


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class CAProfitCalculator:
    """Canada (CA) eBay marketplace profit calculator."""

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
        if inputs.currency and inputs.currency.upper() != "CAD":
            warnings.append(
                f"Currency '{inputs.currency}' is not CAD — "
                f"no FX conversion available"
            )

        store_type = (
            inputs.ca_store_type.value
            if inputs.ca_store_type
            else CA_STORE_NO
        )
        seller_level = inputs.seller_level.value
        destination = (
            inputs.ca_destination.value
            if inputs.ca_destination
            else CA_DEST_DOMESTIC
        )

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

        # --- Resolve FVF rule ---
        rule = resolve_ca_rule(
            store_type, inputs.category, inputs.subcategory
        )

        # --- FVF Base ---
        # Athletic Shoes: sold price only (no shipping, no tax)
        # Otherwise: sold + shipping + tax (Managed Payments total)
        if rule.fvf_base_uses_shipping:
            fvf_base = (
                _d(inputs.sold_price)
                + _d(inputs.shipping_charged)
                + sales_tax
            )
        else:
            fvf_base = _d(inputs.sold_price)

        # --- FVF Calculation ---
        base_fvf = calculate_progressive_fee(fvf_base, rule.tiers)
        base_fvf = apply_seller_level_adjustment(base_fvf, seller_level)

        fvf_per_item = base_fvf / inputs.num_orders
        effective_rate = (
            float(fvf_per_item / fvf_base) if fvf_base > 0 else 0.0
        )

        # --- Transaction Fee (NOT supplied for CA) ---
        transaction_fee = Decimal("0")
        warnings.append(
            "Canada-specific transaction fee rule not supplied — "
            "set to $0"
        )

        # --- International Fee ---
        intl_fee = calculate_ca_international_fee(fvf_base, destination)

        # --- Promoted Listings ---
        promoted_fee = Decimal("0")
        if inputs.promoted_rate > 0:
            # Base assumption: sold price + shipping
            promoted_fee = (
                _d(inputs.sold_price) + _d(inputs.shipping_charged)
            ) * Decimal(str(inputs.promoted_rate / 100.0))
            warnings.append(
                "Canada-specific promoted listing base rule not supplied — "
                "assumed: sold_price + shipping"
            )

        # --- Charity ---
        charity = Decimal("0")
        if inputs.charity_percent > 0:
            charity = _d(inputs.sold_price) * Decimal(
                str(inputs.charity_percent / 100.0)
            )
            warnings.append(
                "Canada-specific charity fee rule not supplied — "
                "assumed: percentage of sold price"
            )

        # --- Currency Conversion (NOT supplied for CA) ---
        currency_fee = Decimal("0")
        if inputs.currency_conversion:
            warnings.append(
                "Canada-specific currency conversion fee rule not supplied "
                "— set to $0"
            )

        # --- Total eBay fees ---
        total_ebay_fees = (
            fvf_per_item + transaction_fee + intl_fee
            + promoted_fee + currency_fee
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
                "Suspiciously high ROI exceeds 500% — "
                "verify source cost and sale price"
            )
        if net_profit < 0:
            warnings.append("Negative profit — this sale loses money")
        if net_profit == 0:
            warnings.append("Zero profit")

        # --- Effective percentages ---
        fvf_pct = self._pct(fvf_per_item, gross_per_item)
        txn_pct = self._pct(transaction_fee, gross_per_item)
        promoted_pct = self._pct(promoted_fee, gross_per_item)
        intl_pct = self._pct(intl_fee, gross_per_item)
        currency_pct = self._pct(currency_fee, gross_per_item)
        charity_pct = self._pct(charity, gross_per_item)
        total_fees_pct = self._pct(total_ebay_fees, gross_per_item)

        # --- Assumptions ---
        assumptions.append("Managed Payments (Canada)")
        assumptions.append(f"Store type: {store_type}")
        assumptions.append(f"Rule matched: {rule.rule_name}")
        if not rule.fvf_base_uses_shipping:
            assumptions.append(
                "FVF calculated on sold price only (Athletic Shoes rule)"
            )
        else:
            assumptions.append(
                "FVF base = sold price + shipping + tax (Managed Payments)"
            )
        if seller_level == "top_rated":
            assumptions.append("Top Rated: 10% FVF discount applied")
        elif seller_level in ("below_standard", "below_average"):
            assumptions.append("Below Average: 5% FVF surcharge applied")
        if destination == "us":
            assumptions.append("International fee: 0.4% (US)")
        elif destination == "other_international":
            assumptions.append("International fee: 1.0% (Other International)")

        # --- Confidence ---
        if _d(inputs.item_cost) == 0 or _d(inputs.sold_price) == 0:
            confidence = "low"
        elif not rule.is_specific_match:
            confidence = "medium"
            warnings.append(
                f"Category '{inputs.category}' used fallback rule "
                f"({rule.rule_name})"
            )
        else:
            confidence = "high"
            
        return ProfitResult(
            marketplace="CA",
            currency="CAD",
            sold_price=_d(inputs.sold_price),
            shipping_charged=_d(inputs.shipping_charged),
            item_cost=_d(inputs.item_cost),
            shipping_cost=_d(inputs.shipping_cost),
            num_orders=inputs.num_orders,
            store_type=store_type,
            seller_level=seller_level,
            overseas_sales=(destination != CA_DEST_DOMESTIC),
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
                transaction_fee=transaction_fee,
                promoted_fee=promoted_fee,
                international_fee=intl_fee,
                charity_cost=charity,
                sales_tax=sales_tax,
                vat_on_fees=Decimal("0"),
                currency_conversion_fee=currency_fee,
                total_fees=total_ebay_fees,
                fvf_pct=fvf_pct,
                transaction_pct=txn_pct,
                promoted_pct=promoted_pct,
                international_pct=intl_pct,
                charity_pct=charity_pct,
                vat_pct=0.0,
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
            confidence=confidence,
            assumptions=assumptions,
            warnings=warnings,
        )

    def _pct(self, amount: Decimal, base: Decimal) -> float:
        if base <= 0:
            return 0.0
        return round(float(amount / base * 100), 2)