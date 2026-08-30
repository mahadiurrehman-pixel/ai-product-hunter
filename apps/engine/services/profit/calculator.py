"""
Profit Calculator with marketplace abstraction.

Calculates profit, fees, margins, and ROI for marketplace sales.
Supports US, UK, DE, and AU eBay marketplaces.

Architecture:
    ProfitCalculator
        ↓
    Marketplace Dispatch
       ├── "US" → _calculate_us()
       ├── "UK" → UKProfitCalculator().calculate()
       ├── "DE" → DEProfitCalculator().calculate()
       └── "AU" → AUProfitCalculator().calculate()
"""
from decimal import Decimal
from typing import List

from utils.logger import get_logger
from .models import (
    FeeBreakdown,
    ProfitInput,
    ProfitResult,
    StoreType,
    SellerLevel,
    TaxType,
)
from .us_fees import (
    calculate_fvf,
    calculate_international_fee,
    calculate_promoted_fee,
    calculate_charity_cost,
)

logger = get_logger(__name__)


def _d(value) -> Decimal:
    """Safely convert any numeric type to Decimal."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class ProfitCalculator:
    """
    Marketplace profit calculator.

    Dispatches calculations to marketplace-specific engines based on the
    inputs.marketplace field. Supported values: "US" (default), "UK",
    "DE", and "AU".
    """
    def calculate(self, inputs: ProfitInput) -> ProfitResult:
        """
        Calculate complete profit breakdown with marketplace dispatch.

        Args:
            inputs: ProfitInput with all parameters

        Returns:
            ProfitResult with full breakdown

        Raises:
            ValueError: If marketplace is unsupported
        """
        marketplace = (inputs.marketplace or "US").upper().strip()

        valid = {"US", "UK", "DE", "AU", "CA"}
        if marketplace not in valid:
            raise ValueError(
                f"Unsupported marketplace '{marketplace}'. Supported: {sorted(valid)}"
            )

        if marketplace == "UK":
            from .uk_calculator import UKProfitCalculator
            return UKProfitCalculator().calculate(inputs)

        if marketplace == "DE":
            from .de_calculator import DEProfitCalculator
            return DEProfitCalculator().calculate(inputs)

        if marketplace == "AU":
            from .au_calculator import AUProfitCalculator
            return AUProfitCalculator().calculate(inputs)

        if marketplace == "CA":
            from .ca_calculator import CAProfitCalculator
            return CAProfitCalculator().calculate(inputs)

        # Default: US calculation engine
        return self._calculate_us(inputs)

    def _calculate_us(self, inputs: ProfitInput) -> ProfitResult:
        """US marketplace calculation engine (original logic)."""
        warnings = []
        assumptions = []

        # Validate inputs
        if inputs.sold_price <= 0:
            warnings.append("Sold price is zero or negative")
        if inputs.item_cost < 0:
            warnings.append("Item cost is negative")
        if inputs.num_orders < 1:
            warnings.append("Number of orders must be at least 1")
            inputs.num_orders = 1

        # Per-item revenue
        gross_per_item = _d(inputs.sold_price) + _d(inputs.shipping_charged)

        # Sales tax calculation
        sales_tax = self._calculate_sales_tax(inputs)

        # FVF calculation
        fvf_base = _d(inputs.sold_price) + _d(inputs.shipping_charged)
        fvf, effective_rate = calculate_fvf(
            sale_amount=fvf_base,
            category=inputs.category,
            store_type=inputs.store_type.value,
            seller_level=inputs.seller_level.value,
            num_orders=inputs.num_orders,
        )
        fvf_per_item = fvf / inputs.num_orders

        # Transaction fee
        per_order_fee = Decimal("0.30") * inputs.num_orders
        transaction_per_item = per_order_fee / inputs.num_orders

        # Promoted listings fee
        # Base includes price + shipping + tax (if tax_includes_shipping)
        if inputs.tax_includes_shipping and sales_tax > 0:
            promoted_base = (
                _d(inputs.sold_price)
                + _d(inputs.shipping_charged)
                + sales_tax
            )
        else:
            promoted_base = (
                _d(inputs.sold_price) + _d(inputs.shipping_charged)
            )
        promoted_fee = calculate_promoted_fee(
            promoted_base, inputs.promoted_rate
        )

        # International fee
        intl_base = _d(inputs.sold_price) + _d(inputs.shipping_charged)
        if inputs.tax_includes_shipping and sales_tax > 0:
            intl_base += sales_tax
        intl_fee = calculate_international_fee(
            intl_base, inputs.overseas_sales
        )

        # Charity
        charity = calculate_charity_cost(
            _d(inputs.sold_price),
            inputs.charity_percent,
            num_orders=1,  # Per item
        )

        # Total fees per item
        total_fees_per_item = (
            fvf_per_item + transaction_per_item + promoted_fee + intl_fee
        )

        # Total costs per item
        total_costs_per_item = (
            _d(inputs.item_cost)
            + _d(inputs.shipping_cost)
            + total_fees_per_item
            + charity
            + _d(inputs.other_costs)
        )

        # Profit per item
        net_profit_per_item = gross_per_item - total_costs_per_item

        # Totals
        total_revenue = gross_per_item * inputs.num_orders
        total_costs = total_costs_per_item * inputs.num_orders
        total_profit = net_profit_per_item * inputs.num_orders

        # Margin and ROI
        if gross_per_item > 0:
            profit_margin = float(net_profit_per_item / gross_per_item * 100)
        else:
            profit_margin = 0.0

        total_investment = _d(inputs.item_cost) + _d(inputs.shipping_cost)
        if total_investment > 0:
            roi = float(net_profit_per_item / total_investment * 100)
        else:
            roi = 0.0

        # Effective percentages
        fvf_pct = self._pct(fvf_per_item, gross_per_item)
        transaction_pct = self._pct(transaction_per_item, gross_per_item)
        promoted_pct = self._pct(promoted_fee, gross_per_item)
        intl_pct = self._pct(intl_fee, gross_per_item)
        charity_pct = self._pct(charity, gross_per_item)
        total_fees_pct = self._pct(total_fees_per_item, gross_per_item)

        # Profit range (best/worst case)
        profit_min, profit_max = self._calculate_range(
            inputs, fvf_per_item, transaction_per_item
        )
        margin_min = self._pct(profit_min, gross_per_item)
        margin_max = self._pct(profit_max, gross_per_item)

        # Confidence
        confidence = self._assess_confidence(inputs)

        # Assumptions
        assumptions.append(
            f"eBay FVF: {effective_rate * 100:.2f}% + $0.30/order"
        )
        if inputs.promoted_rate > 0:
            assumptions.append(
                f"Promoted listings: {inputs.promoted_rate}%"
            )
        if inputs.charity_percent > 0:
            assumptions.append(
                f"Charity donation: {inputs.charity_percent}%"
            )
        if inputs.overseas_sales:
            assumptions.append(
                "International fee: 1.65% applied"
            )
        if inputs.tax_type != TaxType.NONE:
            assumptions.append(
                f"Sales tax: {inputs.tax_rate}% "
                f"({'includes' if inputs.tax_includes_shipping else 'excludes'} shipping)"
            )

        # Warnings
        if inputs.item_cost <= 0:
            warnings.append("Item cost is zero — profit may be inflated")
        if roi > 500:
            warnings.append(
                "ROI exceeds 500% — verify input data accuracy"
            )
        if net_profit_per_item < 0:
            warnings.append("Negative profit — this sale loses money")

        return ProfitResult(
            marketplace=inputs.marketplace,
            currency=inputs.currency,
            sold_price=_d(inputs.sold_price),
            shipping_charged=_d(inputs.shipping_charged),
            item_cost=_d(inputs.item_cost),
            shipping_cost=_d(inputs.shipping_cost),
            num_orders=inputs.num_orders,
            store_type=inputs.store_type.value,
            seller_level=inputs.seller_level.value,
            overseas_sales=inputs.overseas_sales,
            category=inputs.category,
            gross_revenue_per_item=gross_per_item,
            total_revenue=total_revenue,
            total_item_cost=_d(inputs.item_cost) * inputs.num_orders,
            total_shipping_cost=_d(inputs.shipping_cost) * inputs.num_orders,
            fees=FeeBreakdown(
                fvf=fvf_per_item,
                fvf_effective_rate=effective_rate,
                transaction_fee=transaction_per_item,
                promoted_fee=promoted_fee,
                international_fee=intl_fee,
                charity_cost=charity,
                sales_tax=sales_tax,
                total_fees=total_fees_per_item,
                fvf_pct=fvf_pct,
                transaction_pct=transaction_pct,
                promoted_pct=promoted_pct,
                international_pct=intl_pct,
                charity_pct=charity_pct,
                total_fees_pct=total_fees_pct,
            ),
            total_costs=total_costs,
            net_profit_per_item=net_profit_per_item,
            total_profit=total_profit,
            profit_margin=round(profit_margin, 2),
            roi=round(roi, 2),
            is_profitable=net_profit_per_item > 0,
            profit_min=profit_min,
            profit_max=profit_max,
            margin_min=round(margin_min, 2),
            margin_max=round(margin_max, 2),
            confidence=confidence,
            assumptions=assumptions,
            warnings=warnings,
        )

    def _calculate_sales_tax(self, inputs: ProfitInput) -> Decimal:
        """Calculate per-item sales tax."""
        if inputs.tax_type == TaxType.NONE:
            return Decimal("0")

        if inputs.tax_type == TaxType.FIXED:
            return _d(inputs.tax_fixed_amount)

        # Percentage-based
        if inputs.tax_includes_shipping:
            taxable = _d(inputs.sold_price) + _d(inputs.shipping_charged)
        else:
            taxable = _d(inputs.sold_price)

        return taxable * Decimal(str(inputs.tax_rate / 100.0))

    def _calculate_range(
        self,
        inputs: ProfitInput,
        fvf_per_item: Decimal,
        transaction_per_item: Decimal,
    ) -> tuple:
        """
        Calculate best/worst case profit range.

        Best case: lower shipping, no international, no promoted
        Worst case: higher shipping, international, promoted
        """
        gross = _d(inputs.sold_price) + _d(inputs.shipping_charged)

        # Best case
        best_costs = (
            _d(inputs.item_cost)
            + _d(inputs.shipping_cost) * Decimal("0.8")
            + fvf_per_item
            + transaction_per_item
        )
        profit_max = gross - best_costs

        # Worst case
        worst_costs = (
            _d(inputs.item_cost)
            + _d(inputs.shipping_cost) * Decimal("1.3")
            + fvf_per_item * Decimal("1.05")
            + transaction_per_item
            + gross * Decimal("0.0165")  # International
            + gross * Decimal(str(inputs.promoted_rate / 100.0))
            + _d(inputs.other_costs) * 2
        )
        profit_min = gross - worst_costs

        return profit_min, profit_max

    def _assess_confidence(self, inputs: ProfitInput) -> str:
        """Assess confidence in the profit calculation."""
        if inputs.item_cost <= 0:
            return "low"
        if inputs.sold_price <= 0:
            return "low"
        if inputs.shipping_cost <= 0 and inputs.shipping_charged > 0:
            return "medium"  # Shipping cost unknown
        return "high"

    def _pct(self, amount: Decimal, base: Decimal) -> float:
        """Calculate percentage of amount relative to base."""
        if base <= 0:
            return 0.0
        return round(float(amount / base * 100), 2)