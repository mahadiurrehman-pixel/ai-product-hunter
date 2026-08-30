"""Tests for Australia (AU) eBay Profit Calculator — Phase 6D."""
from decimal import Decimal
import pytest

from services.profit import (
    ProfitCalculator,
    ProfitInput,
    AUStoreType,
    SellerLevel,
    TaxType,
    StoreType,
    UKSellerType,
    DESellerType,
)
from services.profit.au_fees import (
    calculate_progressive_fee,
    FeeTier,
    resolve_rate_group,
    calculate_au_transaction_fee,
    apply_top_rated_discount,
    apply_gst_on_fees,
    calculate_au_international_fee,
    calculate_au_currency_conversion,
    AU_STORE_NO,
    AU_STORE_BASIC,
    AU_STORE_FEATURED,
    AU_STORE_ANCHOR,
)


@pytest.fixture
def calc():
    return ProfitCalculator()


def _au(**kwargs):
    defaults = {
        "marketplace": "AU",
        "currency": "AUD",
        "au_store_type": AUStoreType.NO_STORE,
        "seller_level": SellerLevel.ABOVE_STANDARD,
    }
    defaults.update(kwargs)
    return ProfitInput(**defaults)


# =============================================================================
# PROGRESSIVE FEE
# =============================================================================

class TestProgressiveFee:
    def test_below_threshold(self):
        tiers = [FeeTier(4000, 0.134), FeeTier(None, 0.025)]
        fee = calculate_progressive_fee(Decimal("1000"), tiers)
        assert abs(fee - Decimal("134")) < Decimal("0.01")

    def test_above_threshold(self):
        tiers = [FeeTier(4000, 0.134), FeeTier(None, 0.025)]
        fee = calculate_progressive_fee(Decimal("5000"), tiers)
        expected = Decimal("4000") * Decimal("0.134") + Decimal("1000") * Decimal("0.025")
        assert abs(fee - expected) < Decimal("0.01")

    def test_exactly_at_threshold(self):
        tiers = [FeeTier(4000, 0.134), FeeTier(None, 0.025)]
        fee = calculate_progressive_fee(Decimal("4000"), tiers)
        expected = Decimal("4000") * Decimal("0.134")
        assert abs(fee - expected) < Decimal("0.01")

    def test_zero(self):
        tiers = [FeeTier(4000, 0.134), FeeTier(None, 0.025)]
        assert calculate_progressive_fee(Decimal("0"), tiers) == Decimal("0")


# =============================================================================
# RATE GROUP RESOLUTION
# =============================================================================

class TestRateGroup:
    def test_general(self):
        assert resolve_rate_group("antiques") == "general"
        assert resolve_rate_group("clothing") == "general"
        assert resolve_rate_group("books") == "general"

    def test_nft(self):
        assert resolve_rate_group("art", "nft") == "nft"

    def test_cameras_lower(self):
        assert resolve_rate_group("cameras", "digital_cameras") == "cameras_lower"

    def test_cameras_accessories(self):
        assert resolve_rate_group("cameras", "lenses") == "cameras_accessories"

    def test_computers_hardware(self):
        assert resolve_rate_group("computers", "laptops") == "computers_hardware"

    def test_computers_accessories(self):
        assert resolve_rate_group("computers", "cables") == "computers_accessories"

    def test_phones_phones(self):
        assert resolve_rate_group("phones", "mobile_phones") == "phones_phones"

    def test_phones_accessories(self):
        assert resolve_rate_group("phones", "headsets") == "phones_accessories"

    def test_video_consoles(self):
        assert resolve_rate_group("video_games", "consoles") == "video_consoles"

    def test_unknown_falls_to_general(self):
        assert resolve_rate_group("something_random") == "general"


# =============================================================================
# STORE TYPE FVF
# =============================================================================

class TestStoreFVF:
    def test_no_store_general(self, calc):
        inputs = _au(sold_price=Decimal("1000"), item_cost=Decimal("100"))
        r = calc.calculate(inputs)
        # 1000 * 13.4% = 134
        assert abs(r.fees.fvf - Decimal("134")) < Decimal("0.50")

    def test_basic_general(self, calc):
        inputs = _au(
            au_store_type=AUStoreType.BASIC,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
        )
        r = calc.calculate(inputs)
        # 1000 * 11.9% = 119
        assert abs(r.fees.fvf - Decimal("119")) < Decimal("0.50")

    def test_featured_general(self, calc):
        inputs = _au(
            au_store_type=AUStoreType.FEATURED,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
        )
        r = calc.calculate(inputs)
        # 1000 * 10.7% = 107
        assert abs(r.fees.fvf - Decimal("107")) < Decimal("0.50")

    def test_anchor_general(self, calc):
        inputs = _au(
            au_store_type=AUStoreType.ANCHOR,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
        )
        r = calc.calculate(inputs)
        # 1000 * 10.1% = 101
        assert abs(r.fees.fvf - Decimal("101")) < Decimal("0.50")

    def test_above_4000(self, calc):
        inputs = _au(
            sold_price=Decimal("5000"), item_cost=Decimal("500"),
        )
        r = calc.calculate(inputs)
        # 4000*13.4% + 1000*2.5% = 536 + 25 = 561
        assert abs(r.fees.fvf - Decimal("561")) < Decimal("1")


# =============================================================================
# CATEGORY RATES
# =============================================================================

class TestCategoryRates:
    def test_home_appliances_basic(self, calc):
        inputs = _au(
            au_store_type=AUStoreType.BASIC,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            category="home_appliances",
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("73")) < Decimal("0.50")

    def test_nft_no_store(self, calc):
        inputs = _au(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            category="art", subcategory="nft",
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("55")) < Decimal("0.50")

    def test_cameras_lower_featured(self, calc):
        inputs = _au(
            au_store_type=AUStoreType.FEATURED,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            category="cameras", subcategory="digital_cameras",
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("66")) < Decimal("0.50")

    def test_computers_hardware_anchor(self, calc):
        inputs = _au(
            au_store_type=AUStoreType.ANCHOR,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            category="computers", subcategory="laptops",
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("62")) < Decimal("0.50")

    def test_phones_phones_basic(self, calc):
        inputs = _au(
            au_store_type=AUStoreType.BASIC,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            category="phones", subcategory="mobile_phones",
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("73")) < Decimal("0.50")

    def test_video_consoles_featured(self, calc):
        inputs = _au(
            au_store_type=AUStoreType.FEATURED,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            category="video_games", subcategory="consoles",
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("66")) < Decimal("0.50")


# =============================================================================
# TOP RATED DISCOUNT
# =============================================================================

class TestTopRated:
    def test_20_percent_discount(self, calc):
        inputs_tr = _au(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            seller_level=SellerLevel.TOP_RATED,
        )
        inputs_as = _au(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            seller_level=SellerLevel.ABOVE_STANDARD,
        )
        r_tr = calc.calculate(inputs_tr)
        r_as = calc.calculate(inputs_as)
        assert r_tr.fees.fvf < r_as.fees.fvf
        # 134 * 0.80 = 107.20
        assert abs(r_tr.fees.fvf - Decimal("107.20")) < Decimal("0.50")

    def test_below_standard_no_discount(self, calc):
        inputs = _au(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            seller_level=SellerLevel.BELOW_STANDARD,
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.fvf - Decimal("134")) < Decimal("0.50")


# =============================================================================
# TRANSACTION FEE
# =============================================================================

class TestTransactionFee:
    def test_single_order(self):
        assert calculate_au_transaction_fee(1) == Decimal("0.30")

    def test_nine_orders(self):
        assert calculate_au_transaction_fee(9) == Decimal("2.70")

    def test_in_result(self, calc):
        inputs = _au(
            sold_price=Decimal("100"), item_cost=Decimal("10"),
            num_orders=9,
        )
        r = calc.calculate(inputs)
        assert abs(r.fees.transaction_fee - Decimal("0.30")) < Decimal("0.01")


# =============================================================================
# INTERNATIONAL FEE
# =============================================================================

class TestInternational:
    def test_no_overseas(self, calc):
        inputs = _au(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            overseas_sales=False,
        )
        r = calc.calculate(inputs)
        assert r.fees.international_fee == Decimal("0")

    def test_no_store_1_1_percent(self):
        fee = calculate_au_international_fee(
            Decimal("1000"), AU_STORE_NO, True
        )
        assert abs(fee - Decimal("11")) < Decimal("0.01")

    def test_store_1_0_percent(self):
        fee = calculate_au_international_fee(
            Decimal("1000"), AU_STORE_BASIC, True
        )
        assert abs(fee - Decimal("10")) < Decimal("0.01")


# =============================================================================
# CURRENCY CONVERSION
# =============================================================================

class TestCurrencyConversion:
    def test_no_conversion(self, calc):
        inputs = _au(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            currency_conversion=False,
        )
        r = calc.calculate(inputs)
        assert r.fees.currency_conversion_fee == Decimal("0")

    def test_no_store_3_3_percent(self):
        fee = calculate_au_currency_conversion(
            Decimal("1000"), AU_STORE_NO, True
        )
        assert abs(fee - Decimal("33")) < Decimal("0.01")

    def test_store_3_0_percent(self):
        fee = calculate_au_currency_conversion(
            Decimal("1000"), AU_STORE_BASIC, True
        )
        assert abs(fee - Decimal("30")) < Decimal("0.01")


# =============================================================================
# GST
# =============================================================================

class TestGST:
    def test_no_store_includes_gst(self, calc):
        inputs = _au(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            has_abn=False,
        )
        r = calc.calculate(inputs)
        assert r.fees.vat_on_fees == Decimal("0")

    def test_store_with_abn_no_gst(self, calc):
        inputs = _au(
            au_store_type=AUStoreType.BASIC,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            has_abn=True,
        )
        r = calc.calculate(inputs)
        assert r.fees.vat_on_fees == Decimal("0")

    def test_store_without_abn_gst(self, calc):
        inputs = _au(
            au_store_type=AUStoreType.BASIC,
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            has_abn=False,
        )
        r = calc.calculate(inputs)
        assert r.fees.vat_on_fees > Decimal("0")


# =============================================================================
# SALES TAX
# =============================================================================

class TestSalesTax:
    def test_percentage_includes_shipping(self, calc):
        inputs = _au(
            sold_price=Decimal("100"),
            shipping_charged=Decimal("10"),
            item_cost=Decimal("10"),
            tax_type=TaxType.PERCENTAGE,
            tax_rate=10.0,
            tax_includes_shipping=True,
        )
        r = calc.calculate(inputs)
        assert r.fees.sales_tax == Decimal("11")

    def test_percentage_excludes_shipping(self, calc):
        inputs = _au(
            sold_price=Decimal("100"),
            shipping_charged=Decimal("10"),
            item_cost=Decimal("10"),
            tax_type=TaxType.PERCENTAGE,
            tax_rate=10.0,
            tax_includes_shipping=False,
        )
        r = calc.calculate(inputs)
        assert r.fees.sales_tax == Decimal("10")

    def test_fixed(self, calc):
        inputs = _au(
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
            tax_type=TaxType.FIXED,
            tax_fixed_amount=Decimal("8.50"),
        )
        r = calc.calculate(inputs)
        assert r.fees.sales_tax == Decimal("8.50")

    def test_tax_affects_fvf_base(self, calc):
        """Tax included in FVF base per AU rules."""
        inputs_notax = _au(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            tax_type=TaxType.NONE,
        )
        inputs_tax = _au(
            sold_price=Decimal("1000"), item_cost=Decimal("100"),
            tax_type=TaxType.PERCENTAGE, tax_rate=10.0,
            tax_includes_shipping=True,
        )
        r_notax = calc.calculate(inputs_notax)
        r_tax = calc.calculate(inputs_tax)
        assert r_tax.fees.fvf > r_notax.fees.fvf


# =============================================================================
# PROFIT
# =============================================================================

class TestProfit:
    def test_positive(self, calc):
        inputs = _au(
            sold_price=Decimal("500"),
            shipping_charged=Decimal("20"),
            item_cost=Decimal("50"),
            shipping_cost=Decimal("10"),
        )
        r = calc.calculate(inputs)
        assert r.is_profitable
        assert r.net_profit_per_item > 0

    def test_negative(self, calc):
        inputs = _au(
            sold_price=Decimal("50"),
            item_cost=Decimal("200"),
            shipping_cost=Decimal("50"),
        )
        r = calc.calculate(inputs)
        assert not r.is_profitable

    def test_zero_profit(self, calc):
        inputs = _au(
            sold_price=Decimal("10"),
            item_cost=Decimal("100"),
        )
        r = calc.calculate(inputs)
        assert not r.is_profitable

    def test_high_roi_warning(self, calc):
        inputs = _au(
            sold_price=Decimal("10000"),
            item_cost=Decimal("1"),
            shipping_cost=Decimal("1"),
        )
        r = calc.calculate(inputs)
        assert any("500" in w for w in r.warnings)


# =============================================================================
# VALIDATION
# =============================================================================

class TestValidation:
    def test_zero_sold_price(self, calc):
        inputs = _au(sold_price=Decimal("0"), item_cost=Decimal("10"))
        r = calc.calculate(inputs)
        assert any("zero" in w.lower() for w in r.warnings)

    def test_negative_item_cost(self, calc):
        inputs = _au(sold_price=Decimal("100"), item_cost=Decimal("-10"))
        r = calc.calculate(inputs)
        assert any("negative" in w.lower() for w in r.warnings)

    def test_currency_mismatch(self, calc):
        inputs = _au(
            sold_price=Decimal("100"), item_cost=Decimal("10"),
            currency="USD",
        )
        r = calc.calculate(inputs)
        assert any("AUD" in w for w in r.warnings)


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
        assert r.is_profitable

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