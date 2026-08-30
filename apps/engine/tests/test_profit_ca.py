"""Tests for Canada (CA) eBay Profit Calculator — Phase 6E."""
from decimal import Decimal
import pytest

from services.profit import (
    ProfitCalculator,
    ProfitInput,
    CAStoreType,
    CADestination,
    SellerLevel,
    TaxType,
    StoreType,
    UKSellerType,
    DESellerType,
    AUStoreType,
)
from services.profit.ca_fees import (
    calculate_progressive_fee,
    FeeTier,
    resolve_no_store_rule,
    resolve_store_rule,
    apply_seller_level_adjustment,
    calculate_ca_international_fee,
    CA_STORE_NO,
    CA_STORE_BASIC,
    CA_DEST_DOMESTIC,
    CA_DEST_US,
    CA_DEST_OTHER,
)


@pytest.fixture
def calc():
    return ProfitCalculator()


def _ca(**kwargs):
    defaults = {
        "marketplace": "CA",
        "currency": "CAD",
        "ca_store_type": CAStoreType.NO_STORE,
        "seller_level": SellerLevel.ABOVE_STANDARD,
    }
    defaults.update(kwargs)
    return ProfitInput(**defaults)


# =============================================================================
# PROGRESSIVE FEE
# =============================================================================

class TestProgressiveFee:
    def test_below_threshold(self):
        tiers = [FeeTier(2500, 0.1235), FeeTier(None, 0.0235)]
        fee = calculate_progressive_fee(Decimal("1000"), tiers)
        assert abs(fee - Decimal("123.50")) < Decimal("0.01")

    def test_above_threshold(self):
        tiers = [FeeTier(2500, 0.1235), FeeTier(None, 0.0235)]
        fee = calculate_progressive_fee(Decimal("3000"), tiers)
        expected = (
            Decimal("2500") * Decimal("0.1235")
            + Decimal("500") * Decimal("0.0235")
        )
        assert abs(fee - expected) < Decimal("0.01")

    def test_exactly_at_threshold(self):
        tiers = [FeeTier(2500, 0.1235), FeeTier(None, 0.0235)]
        fee = calculate_progressive_fee(Decimal("2500"), tiers)
        expected = Decimal("2500") * Decimal("0.1235")
        assert abs(fee - expected) < Decimal("0.01")

    def test_three_tier_bullion(self):
        tiers = [
            FeeTier(1500, 0.0735),
            FeeTier(10000, 0.05),
            FeeTier(None, 0.045),
        ]
        fee = calculate_progressive_fee(Decimal("15000"), tiers)
        expected = (
            Decimal("1500") * Decimal("0.0735")
            + Decimal("8500") * Decimal("0.05")
            + Decimal("5000") * Decimal("0.045")
        )
        assert abs(fee - expected) < Decimal("0.01")


# =============================================================================
# NO STORE FVF
# =============================================================================

class TestNoStoreFVF:
    def test_everything_else_below_threshold(self, calc):
        inputs = _ca(sold_price=Decimal("100"), item_cost=Decimal("10"))
        r = calc.calculate(inputs)
        # 100 * 13.25% = 13.25
        assert abs(r.fees.fvf - Decimal("13.25")) < Decimal("0.10")

    def test_everything_else_above_threshold(self, calc):
        inputs = _ca(sold_price=Decimal("8000"), item_cost=Decimal("100"))
        r = calc.calculate(inputs)
        # 7499.99 * 13.25% + 500.01 * 2.35%
        expected = (
            Decimal("7499.99") * Decimal("0.1325")
            + Decimal("500.01") * Decimal("0.0235")
        )
        assert abs(r.fees.fvf - expected) < Decimal("0.50")

    def test_art_nft(self, calc):
        inputs = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            category="art", subcategory="art_nft",
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("50")) < Decimal("0.10")

    def test_athletic_shoes_below_150(self, calc):
        inputs = _ca(
            sold_price=Decimal("100"),
            shipping_charged=Decimal("20"),
            item_cost=Decimal("30"),
            category="clothing",
            subcategory="mens_athletic_shoes",
        )
        r = calc.calculate(inputs)
        # 100 * 13.25% = 13.25 (sold price only, no shipping)
        assert abs(r.fees.fvf - Decimal("13.25")) < Decimal("0.10")

    def test_athletic_shoes_above_150(self, calc):
        inputs = _ca(
            sold_price=Decimal("200"),
            item_cost=Decimal("50"),
            category="clothing",
            subcategory="mens_athletic_shoes",
        )
        r = calc.calculate(inputs)
        # 149.99 * 13.25% + 50.01 * 8%
        expected = (
            Decimal("149.99") * Decimal("0.1325")
            + Decimal("50.01") * Decimal("0.08")
        )
        assert abs(r.fees.fvf - expected) < Decimal("0.50")

    def test_guitars_basses(self, calc):
        inputs = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("200"),
            category="musical_instruments",
            subcategory="guitars_basses",
        )
        r = calc.calculate(inputs)
        # 1000 * 6.35% = 63.50
        assert abs(r.fees.fvf - Decimal("63.50")) < Decimal("0.50")

    def test_business_heavy_equipment(self, calc):
        inputs = _ca(
            sold_price=Decimal("20000"), item_cost=Decimal("5000"),
            category="business_industrial",
            subcategory="heavy_equipment",
        )
        r = calc.calculate(inputs)
        # 14999.99 * 3% + 5000.01 * 0.5%
        expected = (
            Decimal("14999.99") * Decimal("0.03")
            + Decimal("5000.01") * Decimal("0.005")
        )
        assert abs(r.fees.fvf - expected) < Decimal("1")


# =============================================================================
# STORE FVF
# =============================================================================

class TestStoreFVF:
    def test_basic_general(self, calc):
        inputs = _ca(
            ca_store_type=CAStoreType.BASIC,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("123.50")) < Decimal("0.50")

    def test_premium_general(self, calc):
        inputs = _ca(
            ca_store_type=CAStoreType.PREMIUM,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("123.50")) < Decimal("0.50")

    def test_anchor_general(self, calc):
        inputs = _ca(
            ca_store_type=CAStoreType.ANCHOR,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("123.50")) < Decimal("0.50")

    def test_basic_books(self, calc):
        inputs = _ca(
            ca_store_type=CAStoreType.BASIC,
            sold_price=Decimal("100"), item_cost=Decimal("10"),
            category="books",
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("13.25")) < Decimal("0.10")

    def test_bullion_progressive(self, calc):
        inputs = _ca(
            ca_store_type=CAStoreType.BASIC,
            sold_price=Decimal("15000"), item_cost=Decimal("13000"),
            category="coins", subcategory="bullion",
        )
        r = calc.calculate(inputs)
        expected = (
            Decimal("1500") * Decimal("0.0735")
            + Decimal("8500") * Decimal("0.05")
            + Decimal("5000") * Decimal("0.045")
        )
        assert abs(r.fees.fvf - expected) < Decimal("2")

    def test_store_computers_hardware(self, calc):
        inputs = _ca(
            ca_store_type=CAStoreType.BASIC,
            sold_price=Decimal("1000"), item_cost=Decimal("500"),
            category="computers", subcategory="laptops",
        )
        r = calc.calculate(inputs)
        # 1000 * 7% = 70
        assert abs(r.fees.fvf - Decimal("70")) < Decimal("0.50")

    def test_store_motors_tires(self, calc):
        inputs = _ca(
            ca_store_type=CAStoreType.BASIC,
            sold_price=Decimal("500"), item_cost=Decimal("100"),
            category="motors", subcategory="tires",
        )
        r = calc.calculate(inputs)
        # 500 * 9% = 45
        assert abs(r.fees.fvf - Decimal("45")) < Decimal("0.50")


# =============================================================================
# SELLER LEVEL
# =============================================================================

class TestSellerLevel:
    def test_top_rated_discount(self, calc):
        inputs_tr = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            seller_level=SellerLevel.TOP_RATED,
        )
        inputs_as = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            seller_level=SellerLevel.ABOVE_STANDARD,
        )
        r_tr = calc.calculate(inputs_tr)
        r_as = calc.calculate(inputs_as)
        # 132.50 * 0.90 = 119.25
        assert abs(r_tr.fees.fvf - Decimal("119.25")) < Decimal("0.50")
        assert r_tr.fees.fvf < r_as.fees.fvf

    def test_below_average_surcharge(self, calc):
        inputs_ba = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            seller_level=SellerLevel.BELOW_STANDARD,
        )
        inputs_as = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            seller_level=SellerLevel.ABOVE_STANDARD,
        )
        r_ba = calc.calculate(inputs_ba)
        r_as = calc.calculate(inputs_as)
        # 132.50 * 1.05 = 139.125
        assert abs(r_ba.fees.fvf - Decimal("139.125")) < Decimal("0.50")
        assert r_ba.fees.fvf > r_as.fees.fvf

    def test_above_standard_no_change(self, calc):
        inputs = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            seller_level=SellerLevel.ABOVE_STANDARD,
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("132.50")) < Decimal("0.50")

    def test_adjustment_helper(self):
        fvf = Decimal("100")
        assert apply_seller_level_adjustment(fvf, "top_rated") == Decimal("90")
        assert apply_seller_level_adjustment(fvf, "above_standard") == Decimal("100")
        assert apply_seller_level_adjustment(fvf, "below_standard") == Decimal("105")


# =============================================================================
# INTERNATIONAL FEE
# =============================================================================

class TestInternational:
    def test_domestic_no_fee(self, calc):
        inputs = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            ca_destination=CADestination.DOMESTIC,
        )
        r = calc.calculate(inputs)
        assert r.fees.international_fee == Decimal("0")

    def test_us_04_percent(self):
        fee = calculate_ca_international_fee(Decimal("1000"), CA_DEST_US)
        assert abs(fee - Decimal("4")) < Decimal("0.01")

    def test_other_10_percent(self):
        fee = calculate_ca_international_fee(Decimal("1000"), CA_DEST_OTHER)
        assert abs(fee - Decimal("10")) < Decimal("0.01")

    def test_us_in_result(self, calc):
        inputs = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            ca_destination=CADestination.US,
        )
        r = calc.calculate(inputs)
        # 1000 * 0.4% = 4
        assert abs(r.fees.international_fee - Decimal("4")) < Decimal("0.10")

    def test_other_in_result(self, calc):
        inputs = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            ca_destination=CADestination.OTHER_INTERNATIONAL,
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.international_fee - Decimal("10")) < Decimal("0.10")


# =============================================================================
# THRESHOLD BOUNDARIES
# =============================================================================

class TestThresholds:
    def test_149_99_athletic(self, calc):
        inputs = _ca(
            sold_price=Decimal("149.99"), item_cost=Decimal("30"),
            category="clothing", subcategory="mens_athletic_shoes",
        )
        r = calc.calculate(inputs)
        # All at 13.25%
        expected = Decimal("149.99") * Decimal("0.1325")
        assert abs(r.fees.fvf - expected) < Decimal("0.10")

    def test_150_athletic(self, calc):
        inputs = _ca(
            sold_price=Decimal("150"), item_cost=Decimal("30"),
            category="clothing", subcategory="mens_athletic_shoes",
        )
        r = calc.calculate(inputs)
        # 149.99 at 13.25% + 0.01 at 8%
        expected = (
            Decimal("149.99") * Decimal("0.1325")
            + Decimal("0.01") * Decimal("0.08")
        )
        assert abs(r.fees.fvf - expected) < Decimal("0.10")

    def test_2500_boundary(self, calc):
        inputs = _ca(
            ca_store_type=CAStoreType.BASIC,
            sold_price=Decimal("2500"), item_cost=Decimal("500"),
        )
        r = calc.calculate(inputs)
        expected = Decimal("2500") * Decimal("0.1235")
        assert abs(r.fees.fvf - expected) < Decimal("0.50")

    def test_7500_boundary_no_store(self, calc):
        inputs = _ca(
            sold_price=Decimal("7500"), item_cost=Decimal("1000"),
        )
        r = calc.calculate(inputs)
        expected = (
            Decimal("7499.99") * Decimal("0.1325")
            + Decimal("0.01") * Decimal("0.0235")
        )
        assert abs(r.fees.fvf - expected) < Decimal("0.50")


# =============================================================================
# SALES TAX
# =============================================================================

class TestSalesTax:
    def test_percentage_includes_shipping(self, calc):
        inputs = _ca(
            sold_price=Decimal("100"),
            shipping_charged=Decimal("10"),
            item_cost=Decimal("10"),
            tax_type=TaxType.PERCENTAGE,
            tax_rate=13.0,
            tax_includes_shipping=True,
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.sales_tax - Decimal("14.30")) < Decimal("0.01")

    def test_percentage_excludes_shipping(self, calc):
        inputs = _ca(
            sold_price=Decimal("100"),
            shipping_charged=Decimal("10"),
            item_cost=Decimal("10"),
            tax_type=TaxType.PERCENTAGE,
            tax_rate=13.0,
            tax_includes_shipping=False,
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.sales_tax - Decimal("13")) < Decimal("0.01")

    def test_fixed(self, calc):
        inputs = _ca(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            tax_type=TaxType.FIXED,
            tax_fixed_amount=Decimal("13"),
        )
        r = calc.calculate(inputs)
        assert r.fees.sales_tax == Decimal("13")

    def test_tax_included_in_fvf_base(self, calc):
        inputs_notax = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
        )
        inputs_tax = _ca(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            tax_type=TaxType.PERCENTAGE, tax_rate=13.0,
            tax_includes_shipping=True,
        )
        r_notax = calc.calculate(inputs_notax)
        r_tax = calc.calculate(inputs_tax)
        # Tax should increase FVF base
        assert r_tax.fees.fvf > r_notax.fees.fvf


# =============================================================================
# UNSUPPORTED RULES
# =============================================================================

class TestUnsupportedRules:
    def test_transaction_fee_warning(self, calc):
        inputs = _ca(sold_price=Decimal("100"), item_cost=Decimal("10"))
        r = calc.calculate(inputs)
        assert any("transaction fee" in w.lower() for w in r.warnings)
        assert r.fees.transaction_fee == Decimal("0")

    def test_promoted_warning(self, calc):
        inputs = _ca(
            sold_price=Decimal("100"), item_cost=Decimal("10"),
            promoted_rate=10.0,
        )
        r = calc.calculate(inputs)
        assert any("promoted" in w.lower() for w in r.warnings)

    def test_charity_warning(self, calc):
        inputs = _ca(
            sold_price=Decimal("100"), item_cost=Decimal("10"),
            charity_percent=10.0,
        )
        r = calc.calculate(inputs)
        assert any("charity" in w.lower() for w in r.warnings)

    def test_currency_conversion_warning(self, calc):
        inputs = _ca(
            sold_price=Decimal("100"), item_cost=Decimal("10"),
            currency_conversion=True,
        )
        r = calc.calculate(inputs)
        assert any("currency conversion" in w.lower() for w in r.warnings)
        assert r.fees.currency_conversion_fee == Decimal("0")


# =============================================================================
# PROFIT
# =============================================================================

class TestProfit:
    def test_positive(self, calc):
        inputs = _ca(
            sold_price=Decimal("500"),
            shipping_charged=Decimal("20"),
            item_cost=Decimal("50"),
            shipping_cost=Decimal("10"),
        )
        r = calc.calculate(inputs)
        assert r.is_profitable
        assert r.net_profit_per_item > 0

    def test_negative(self, calc):
        inputs = _ca(
            sold_price=Decimal("50"),
            item_cost=Decimal("200"),
            shipping_cost=Decimal("50"),
        )
        r = calc.calculate(inputs)
        assert not r.is_profitable

    def test_zero_profit(self, calc):
        inputs = _ca(
            sold_price=Decimal("10"),
            item_cost=Decimal("100"),
        )
        r = calc.calculate(inputs)
        assert not r.is_profitable

    def test_high_roi(self, calc):
        inputs = _ca(
            sold_price=Decimal("10000"),
            item_cost=Decimal("1"),
            shipping_cost=Decimal("1"),
        )
        r = calc.calculate(inputs)
        assert any("500" in w for w in r.warnings)

    def test_multiple_orders(self, calc):
        inputs = _ca(
            sold_price=Decimal("100"), item_cost=Decimal("20"),
            num_orders=9,
        )
        r = calc.calculate(inputs)
        assert r.num_orders == 9
        assert r.total_revenue == Decimal("900")


# =============================================================================
# CONFIDENCE
# =============================================================================

class TestConfidence:
    def test_high_confidence(self, calc):
        inputs = _ca(
            sold_price=Decimal("500"), item_cost=Decimal("100"),
            category="music", subcategory="vinyl_records",
            ca_store_type=CAStoreType.BASIC,
        )
        r = calc.calculate(inputs)
        assert r.confidence == "high"

    def test_low_confidence_zero_cost(self, calc):
        inputs = _ca(sold_price=Decimal("100"), item_cost=Decimal("0"))
        r = calc.calculate(inputs)
        assert r.confidence == "low"


# =============================================================================
# VALIDATION
# =============================================================================

class TestValidation:
    def test_zero_sold_price(self, calc):
        inputs = _ca(sold_price=Decimal("0"), item_cost=Decimal("10"))
        r = calc.calculate(inputs)
        assert any("zero" in w.lower() for w in r.warnings)

    def test_negative_item_cost(self, calc):
        inputs = _ca(sold_price=Decimal("100"), item_cost=Decimal("-10"))
        r = calc.calculate(inputs)
        assert any("negative" in w.lower() for w in r.warnings)

    def test_currency_mismatch(self, calc):
        inputs = _ca(
            sold_price=Decimal("100"), item_cost=Decimal("10"),
            currency="USD",
        )
        r = calc.calculate(inputs)
        assert any("CAD" in w for w in r.warnings)


# =============================================================================
# REGRESSION
# =============================================================================

class TestRegression:
    def test_us_untouched(self, calc):
        r = calc.calculate(ProfitInput(
            marketplace="US", sold_price=Decimal("100"),
            item_cost=Decimal("10"), store_type=StoreType.NO_STORE,
        ))
        assert r.marketplace == "US"

    def test_uk_untouched(self, calc):
        r = calc.calculate(ProfitInput(
            marketplace="UK", currency="GBP",
            uk_seller_type=UKSellerType.BUSINESS,
            sold_price=Decimal("100"), item_cost=Decimal("10"),
        ))
        assert r.marketplace == "UK"

    def test_de_untouched(self, calc):
        r = calc.calculate(ProfitInput(
            marketplace="DE", currency="EUR",
            de_seller_type=DESellerType.COMMERCIAL,
            sold_price=Decimal("100"), item_cost=Decimal("10"),
        ))
        assert r.marketplace == "DE"

    def test_au_untouched(self, calc):
        r = calc.calculate(ProfitInput(
            marketplace="AU", currency="AUD",
            au_store_type=AUStoreType.NO_STORE,
            sold_price=Decimal("100"), item_cost=Decimal("10"),
        ))
        assert r.marketplace == "AU"