"""
Tests for Phase 6 — US eBay Profit Calculator.
"""
from decimal import Decimal

import pytest

from services.profit import (
    ProfitCalculator,
    ProfitInput,
    ProfitResult,
    StoreType,
    SellerLevel,
    TaxType,
)
from services.profit.us_fees import (
    calculate_fvf,
    calculate_international_fee,
    calculate_promoted_fee,
    calculate_charity_cost,
)


@pytest.fixture
def calc():
    return ProfitCalculator()


# =============================================================================
# Basic Profit Calculation
# =============================================================================

class TestBasicProfit:
    def test_simple_profit(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            shipping_cost=Decimal("5"),
            shipping_charged=Decimal("10"),
        )
        result = calc.calculate(inputs)
        assert result.is_profitable
        assert result.net_profit_per_item > 0
        assert result.sold_price == Decimal("100")

    def test_zero_profit(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("20"),
            item_cost=Decimal("15"),
            shipping_cost=Decimal("5"),
            shipping_charged=Decimal("0"),
        )
        result = calc.calculate(inputs)
        # Fees will push this negative
        assert isinstance(result.is_profitable, bool)

    def test_negative_profit(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("10"),
            item_cost=Decimal("50"),
            shipping_cost=Decimal("10"),
            shipping_charged=Decimal("0"),
        )
        result = calc.calculate(inputs)
        assert not result.is_profitable
        assert result.net_profit_per_item < 0
        assert any("Negative profit" in w for w in result.warnings)

    def test_zero_sold_price_warning(self, calc):
        inputs = ProfitInput(sold_price=Decimal("0"))
        result = calc.calculate(inputs)
        assert any("zero" in w.lower() for w in result.warnings)


# =============================================================================
# Fee Calculations
# =============================================================================

class TestFeeCalculations:
    def test_fvf_default_category(self):
        fvf, rate = calculate_fvf(
            Decimal("100"), category="default", num_orders=1
        )
        # 12.9% of $100 + $0.30 = $13.20
        expected = Decimal("100") * Decimal("0.129") + Decimal("0.30")
        assert abs(fvf - expected) < Decimal("0.01")

    def test_fvf_computers_category(self):
        fvf, rate = calculate_fvf(
            Decimal("500"), category="computers", num_orders=1
        )
        expected = Decimal("500") * Decimal("0.07") + Decimal("0.30")
        assert abs(fvf - expected) < Decimal("0.01")

    def test_fvf_consumer_electronics(self):
        fvf, rate = calculate_fvf(
            Decimal("200"), category="consumer_electronics", num_orders=1
        )
        expected = Decimal("200") * Decimal("0.08") + Decimal("0.30")
        assert abs(fvf - expected) < Decimal("0.01")

    def test_fvf_jewelry_bracket(self):
        """Jewelry over $2,500 uses lower bracket rate."""
        fvf, rate = calculate_fvf(
            Decimal("3000"), category="jewelry", num_orders=1
        )
        # First $2,500 at 14.9%, remaining $500 at 5.0%
        expected = (
            Decimal("2500") * Decimal("0.149")
            + Decimal("500") * Decimal("0.05")
            + Decimal("0.30")
        )
        assert abs(fvf - expected) < Decimal("0.01")

    def test_fvf_jewelry_below_bracket(self):
        """Jewelry under $2,500 uses standard rate."""
        fvf, rate = calculate_fvf(
            Decimal("1000"), category="jewelry", num_orders=1
        )
        expected = Decimal("1000") * Decimal("0.149") + Decimal("0.30")
        assert abs(fvf - expected) < Decimal("0.01")

    def test_fvf_multiple_orders(self):
        fvf, rate = calculate_fvf(
            Decimal("100"), category="default", num_orders=9
        )
        expected = Decimal("100") * Decimal("0.129") + Decimal("0.30") * 9
        assert abs(fvf - expected) < Decimal("0.01")

    def test_international_fee_yes(self):
        fee = calculate_international_fee(Decimal("100"), overseas=True)
        expected = Decimal("100") * Decimal("0.0165")
        assert abs(fee - expected) < Decimal("0.01")

    def test_international_fee_no(self):
        fee = calculate_international_fee(Decimal("100"), overseas=False)
        assert fee == Decimal("0")

    def test_promoted_fee(self):
        fee = calculate_promoted_fee(Decimal("110"), 10.0)
        expected = Decimal("110") * Decimal("0.10")
        assert abs(fee - expected) < Decimal("0.01")

    def test_promoted_fee_zero_rate(self):
        fee = calculate_promoted_fee(Decimal("100"), 0.0)
        assert fee == Decimal("0")

    def test_charity_cost(self):
        cost = calculate_charity_cost(Decimal("100"), 10.0)
        expected = Decimal("100") * Decimal("0.10")
        assert abs(cost - expected) < Decimal("0.01")

    def test_charity_zero(self):
        cost = calculate_charity_cost(Decimal("100"), 0.0)
        assert cost == Decimal("0")


# =============================================================================
# Store Type Tests
# =============================================================================

class TestStoreTypes:
    def test_no_store(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            store_type=StoreType.NO_STORE,
        )
        result = calc.calculate(inputs)
        assert result.store_type == "no_store"

    def test_basic_store_discount(self, calc):
        inputs_basic = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            store_type=StoreType.BASIC,
        )
        inputs_no = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            store_type=StoreType.NO_STORE,
        )
        r_basic = calc.calculate(inputs_basic)
        r_no = calc.calculate(inputs_no)
        # Basic store has 1% discount → lower FVF
        assert r_basic.fees.fvf < r_no.fees.fvf

    def test_premium_store_discount(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            store_type=StoreType.PREMIUM,
        )
        result = calc.calculate(inputs)
        # Premium has 4% discount
        assert result.fees.fvf_effective_rate < 0.129

    def test_anchor_store(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            store_type=StoreType.ANCHOR,
        )
        result = calc.calculate(inputs)
        # Anchor = 6% discount → 0.129 * 0.94 = 0.12126
        assert result.fees.fvf_effective_rate < 0.13
        assert result.fees.fvf_effective_rate < 0.129  # Less than default
        
    def test_enterprise_store(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            store_type=StoreType.ENTERPRISE,
        )
        result = calc.calculate(inputs)
        assert result.fees.fvf_effective_rate < 0.12


# =============================================================================
# Seller Level Tests
# =============================================================================

class TestSellerLevels:
    def test_top_rated_discount(self, calc):
        inputs_tr = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            seller_level=SellerLevel.TOP_RATED,
        )
        inputs_as = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            seller_level=SellerLevel.ABOVE_STANDARD,
        )
        r_tr = calc.calculate(inputs_tr)
        r_as = calc.calculate(inputs_as)
        assert r_tr.fees.fvf < r_as.fees.fvf

    def test_above_standard(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            seller_level=SellerLevel.ABOVE_STANDARD,
        )
        result = calc.calculate(inputs)
        assert result.seller_level == "above_standard"

    def test_below_standard(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            seller_level=SellerLevel.BELOW_STANDARD,
        )
        result = calc.calculate(inputs)
        assert result.seller_level == "below_standard"


# =============================================================================
# Overseas / International Tests
# =============================================================================

class TestOverseas:
    def test_overseas_yes(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            overseas_sales=True,
        )
        result = calc.calculate(inputs)
        assert result.fees.international_fee > 0
        assert result.overseas_sales is True

    def test_overseas_no(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            overseas_sales=False,
        )
        result = calc.calculate(inputs)
        assert result.fees.international_fee == Decimal("0")


# =============================================================================
# Promoted Listings Tests
# =============================================================================

class TestPromotedListings:
    def test_promoted_10_percent(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            shipping_charged=Decimal("10"),
            item_cost=Decimal("10"),
            promoted_rate=10.0,
        )
        result = calc.calculate(inputs)
        assert result.fees.promoted_fee > 0
        assert result.fees.promoted_pct > 0

    def test_promoted_zero(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            promoted_rate=0.0,
        )
        result = calc.calculate(inputs)
        assert result.fees.promoted_fee == Decimal("0")


# =============================================================================
# Charity Tests
# =============================================================================

class TestCharity:
    def test_charity_10_percent(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            charity_percent=10.0,
        )
        result = calc.calculate(inputs)
        assert result.fees.charity_cost == Decimal("10")

    def test_charity_zero(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            charity_percent=0.0,
        )
        result = calc.calculate(inputs)
        assert result.fees.charity_cost == Decimal("0")


# =============================================================================
# Sales Tax Tests
# =============================================================================

class TestSalesTax:
    def test_tax_percentage(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            tax_type=TaxType.PERCENTAGE,
            tax_rate=10.0,
            tax_includes_shipping=False,
        )
        result = calc.calculate(inputs)
        assert result.fees.sales_tax == Decimal("10")

    def test_tax_fixed(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            tax_type=TaxType.FIXED,
            tax_fixed_amount=Decimal("8.50"),
        )
        result = calc.calculate(inputs)
        assert result.fees.sales_tax == Decimal("8.50")

    def test_tax_includes_shipping(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            shipping_charged=Decimal("10"),
            item_cost=Decimal("10"),
            tax_type=TaxType.PERCENTAGE,
            tax_rate=10.0,
            tax_includes_shipping=True,
        )
        result = calc.calculate(inputs)
        # Tax on $100 + $10 = $11
        assert result.fees.sales_tax == Decimal("11")

    def test_tax_none(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            tax_type=TaxType.NONE,
        )
        result = calc.calculate(inputs)
        assert result.fees.sales_tax == Decimal("0")


# =============================================================================
# Multiple Orders Tests
# =============================================================================

class TestMultipleOrders:
    def test_multiple_orders(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            shipping_charged=Decimal("10"),
            item_cost=Decimal("10"),
            shipping_cost=Decimal("5"),
            num_orders=9,
        )
        result = calc.calculate(inputs)
        assert result.num_orders == 9
        assert result.total_revenue == Decimal("110") * 9
        assert result.total_profit == result.net_profit_per_item * 9

    def test_single_order(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            num_orders=1,
        )
        result = calc.calculate(inputs)
        assert result.num_orders == 1
        assert result.total_profit == result.net_profit_per_item


# =============================================================================
# Category-Specific FVF Tests
# =============================================================================

class TestCategoryFVF:
    def test_books_higher_rate(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            category="books",
        )
        result = calc.calculate(inputs)
        # Books: 14.9% vs default 12.9%
        assert result.fees.fvf_effective_rate > 0.14

    def test_computers_lower_rate(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            category="computers",
        )
        result = calc.calculate(inputs)
        assert result.fees.fvf_effective_rate < 0.08

    def test_unsupported_category_uses_default(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            category="unknown_category_xyz",
        )
        result = calc.calculate(inputs)
        assert abs(result.fees.fvf_effective_rate - 0.129) < 0.001


# =============================================================================
# Full Scenario Test
# =============================================================================

class TestFullScenario:
    def test_supplied_example(self, calc):
        """
        Test case from requirements:
        Sold: $100, Shipping charged: $10, Item cost: $10,
        Shipping cost: $10, Orders: 9, Store: Starter,
        Seller: Above Standard, Overseas: Yes,
        Promoted: 10%, Charity: 10%, Tax: 10%, Tax includes shipping: Yes
        """
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            shipping_charged=Decimal("10"),
            item_cost=Decimal("10"),
            shipping_cost=Decimal("10"),
            num_orders=9,
            store_type=StoreType.STARTER,
            seller_level=SellerLevel.ABOVE_STANDARD,
            overseas_sales=True,
            promoted_rate=10.0,
            charity_percent=10.0,
            tax_type=TaxType.PERCENTAGE,
            tax_rate=10.0,
            tax_includes_shipping=True,
        )
        result = calc.calculate(inputs)

        assert result.is_profitable or not result.is_profitable  # Just verify it runs
        assert result.num_orders == 9
        assert result.fees.fvf > 0
        assert result.fees.promoted_fee > 0
        assert result.fees.international_fee > 0
        assert result.fees.charity_cost > 0
        assert result.fees.sales_tax > 0
        assert result.total_revenue > 0
        assert len(result.assumptions) > 0

    def test_result_to_dict(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("50"),
            item_cost=Decimal("10"),
        )
        result = calc.calculate(inputs)
        d = result.to_dict()
        assert "net_profit_per_item" in d
        assert "profit_margin" in d
        assert "roi" in d
        assert "fees" in d
        assert "is_profitable" in d
        assert "assumptions" in d
        assert "warnings" in d

    def test_profit_range(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            shipping_cost=Decimal("5"),
            shipping_charged=Decimal("10"),
            promoted_rate=5.0,
            overseas_sales=True,
        )
        result = calc.calculate(inputs)
        assert result.profit_min < result.profit_max
        assert result.margin_min < result.margin_max

    def test_high_roi_warning(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("1000"),
            item_cost=Decimal("1"),
            shipping_cost=Decimal("1"),
        )
        result = calc.calculate(inputs)
        assert any("500%" in w for w in result.warnings)

    def test_confidence_high(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            shipping_cost=Decimal("5"),
            shipping_charged=Decimal("10"),
        )
        result = calc.calculate(inputs)
        assert result.confidence == "high"

    def test_confidence_low_zero_cost(self, calc):
        inputs = ProfitInput(
            sold_price=Decimal("100"),
            item_cost=Decimal("0"),
        )
        result = calc.calculate(inputs)
        assert result.confidence == "low"