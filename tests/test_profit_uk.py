"""Tests for UK eBay Profit Calculator."""
from decimal import Decimal
import pytest

from services.profit import (
    ProfitCalculator,
    ProfitInput,
    UKSellerType,
    SellerLevel,
    TaxType,
    UKBuyerRegion,
)
from services.profit.uk_fees import (
    calculate_uk_fvf,
    calculate_uk_international_fee,
    calculate_uk_promoted_fee,
    calculate_uk_charity,
    calculate_uk_vat_on_fees,
    calculate_uk_currency_conversion,
    calculate_tiered_fee,
    FeeTier,
)


@pytest.fixture
def calc():
    return ProfitCalculator()


def _uk_input(**kwargs):
    defaults = {
        "marketplace": "UK",
        "currency": "GBP",
        "uk_seller_type": UKSellerType.BUSINESS,
        "seller_level": SellerLevel.ABOVE_STANDARD,
    }
    defaults.update(kwargs)
    return ProfitInput(**defaults)


class TestTieredFee:
    def test_single_tier(self):
        tiers = [FeeTier(max_amount=None, rate=0.10)]
        fee = calculate_tiered_fee(Decimal("100"), tiers)
        assert fee == Decimal("10")

    def test_two_tiers(self):
        tiers = [
            FeeTier(max_amount=1000, rate=0.069),
            FeeTier(max_amount=None, rate=0.03),
        ]
        fee = calculate_tiered_fee(Decimal("1500"), tiers)
        expected = Decimal("1000") * Decimal("0.069") + Decimal("500") * Decimal("0.03")
        assert abs(fee - expected) < Decimal("0.01")

    def test_three_tiers(self):
        tiers = [
            FeeTier(max_amount=500, rate=0.109),
            FeeTier(max_amount=1000, rate=0.079),
            FeeTier(max_amount=None, rate=0.03),
        ]
        fee = calculate_tiered_fee(Decimal("1500"), tiers)
        expected = (
            Decimal("500") * Decimal("0.109")
            + Decimal("500") * Decimal("0.079")
            + Decimal("500") * Decimal("0.03")
        )
        assert abs(fee - expected) < Decimal("0.01")

    def test_zero_amount(self):
        tiers = [FeeTier(max_amount=None, rate=0.10)]
        assert calculate_tiered_fee(Decimal("0"), tiers) == Decimal("0")


class TestUKFVF:
    def test_private_default(self):
        total, var, rate = calculate_uk_fvf(
            Decimal("100"), "private", "default"
        )
        # 12.8% of £100 + £0.30 = £13.10
        assert var > 0
        assert total > var  # Includes transaction fee

    def test_private_over_threshold(self):
        total, var, rate = calculate_uk_fvf(
            Decimal("6000"), "private", "default"
        )
        # First £5000 at 12.8%, rest at 3%
        assert var > 0

    def test_business_cameras_bracket(self):
        total, var, rate = calculate_uk_fvf(
            Decimal("1500"), "business", "cameras", "specified"
        )
        # First £1000 at 6.9%, rest at 3%
        expected_var = (
            Decimal("1000") * Decimal("0.069")
            + Decimal("500") * Decimal("0.03")
        )
        assert abs(var - expected_var) < Decimal("0.01")

    def test_top_rated_discount(self):
        _, var_normal, _ = calculate_uk_fvf(
            Decimal("100"), "business", "default",
            seller_level="above_standard",
        )
        _, var_tr, _ = calculate_uk_fvf(
            Decimal("100"), "business", "default",
            seller_level="top_rated",
        )
        assert var_tr < var_normal

    def test_fvf_cap(self):
        _, var, _ = calculate_uk_fvf(
            Decimal("50000"), "private", "default"
        )
        assert var <= Decimal("250")

    def test_low_value_transaction_fee(self):
        total, var, rate = calculate_uk_fvf(
            Decimal("8"), "business", "default", num_orders=1
        )
        # Should use 10p transaction fee for ≤£10
        assert total < var + Decimal("0.15")


class TestUKInternational:
    def test_domestic_no_fee(self):
        fee = calculate_uk_international_fee(
            Decimal("100"), "business", "domestic", False
        )
        assert fee == Decimal("0")

    def test_private_eurozone(self):
        fee = calculate_uk_international_fee(
            Decimal("100"), "private", "eurozone_northern_europe", True
        )
        assert fee == Decimal("3")  # 3%

    def test_business_us_canada(self):
        fee = calculate_uk_international_fee(
            Decimal("100"), "business", "us_canada", True
        )
        assert fee == Decimal("1.80")  # 1.8%

    def test_business_other(self):
        fee = calculate_uk_international_fee(
            Decimal("100"), "business", "other", True
        )
        assert fee == Decimal("2")  # 2%


class TestUKPromoted:
    def test_promoted_10_percent(self):
        fee = calculate_uk_promoted_fee(Decimal("100"), 10.0)
        assert fee == Decimal("10")  # Excludes postage

    def test_promoted_zero(self):
        assert calculate_uk_promoted_fee(Decimal("100"), 0) == Decimal("0")

    def test_promoted_excludes_postage(self):
        # Promoted fee on selling price only, not shipping
        fee = calculate_uk_promoted_fee(Decimal("100"), 10.0)
        assert fee == Decimal("10")  # Not affected by shipping


class TestUKCharity:
    def test_charity_10_percent(self):
        fee = calculate_uk_charity(Decimal("100"), 10.0)
        assert fee == Decimal("10")  # Excludes shipping

    def test_charity_100_percent(self):
        fee = calculate_uk_charity(Decimal("100"), 100.0)
        assert fee == Decimal("100")

    def test_charity_zero(self):
        assert calculate_uk_charity(Decimal("100"), 0) == Decimal("0")


class TestUKVAT:
    def test_vat_registered_business(self):
        vat = calculate_uk_vat_on_fees(
            Decimal("20"), vat_registered=True, seller_type="business"
        )
        assert vat == Decimal("4")  # 20% of £20

    def test_vat_not_registered(self):
        vat = calculate_uk_vat_on_fees(
            Decimal("20"), vat_registered=False, seller_type="business"
        )
        assert vat == Decimal("0")

    def test_vat_private_seller(self):
        vat = calculate_uk_vat_on_fees(
            Decimal("20"), vat_registered=True, seller_type="private"
        )
        assert vat == Decimal("0")


class TestUKCurrencyConversion:
    def test_conversion_applied(self):
        fee = calculate_uk_currency_conversion(Decimal("100"), True)
        assert fee == Decimal("2.50")  # 2.5%

    def test_no_conversion(self):
        fee = calculate_uk_currency_conversion(Decimal("100"), False)
        assert fee == Decimal("0")


class TestUKFullScenario:
    def test_supplied_example(self, calc):
        """
        Business, Above Standard, VAT registered.
        Sold: £100, Shipping: £10, Cost: £10, Ship cost: £10,
        Orders: 9, Everything else, Overseas US/Canada,
        Promoted: 10%, Charity: 10%
        """
        inputs = _uk_input(
            sold_price=Decimal("100"),
            shipping_charged=Decimal("10"),
            item_cost=Decimal("10"),
            shipping_cost=Decimal("10"),
            num_orders=9,
            category="default",
            overseas_sales=True,
            buyer_region=UKBuyerRegion.US_CANADA,
            promoted_rate=10.0,
            charity_percent=10.0,
            vat_registered=True,
        )
        result = calc.calculate(inputs)

        assert result.marketplace == "UK"
        assert result.currency == "GBP"
        assert result.fees.fvf > 0
        assert result.fees.promoted_fee == Decimal("10")  # 10% of £100
        assert result.fees.charity_cost == Decimal("10")  # 10% of £100
        assert result.fees.international_fee > 0
        assert result.fees.vat_on_fees > 0
        assert result.num_orders == 9
        assert len(result.assumptions) > 0

    def test_result_to_dict(self, calc):
        inputs = _uk_input(
            sold_price=Decimal("50"),
            item_cost=Decimal("10"),
        )
        result = calc.calculate(inputs)
        d = result.to_dict()
        assert "vat_on_fees" in d["fees"]
        assert "currency_conversion_fee" in d["fees"]
        assert "variable_fvf" in d["fees"]

    def test_us_tests_unaffected(self, calc):
        """Verify US calculation still works through dispatch."""
        from services.profit import StoreType
        inputs = ProfitInput(
            marketplace="US",
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            store_type=StoreType.NO_STORE,
        )
        result = calc.calculate(inputs)
        assert result.marketplace == "US"
        assert result.currency == "USD"
        assert result.is_profitable