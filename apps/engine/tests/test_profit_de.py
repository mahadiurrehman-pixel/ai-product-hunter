"""Tests for Germany (DE) eBay Profit Calculator — Phase 6C."""
from decimal import Decimal
import pytest

from services.profit import (
    ProfitCalculator,
    ProfitInput,
    DESellerType,
    DEBuyerRegion,
    SellerLevel,
    TaxType,
    StoreType,
    UKSellerType,
)
from services.profit.de_fees import (
    calculate_tiered_fee,
    FeeTier,
    is_excluded_category,
    get_de_commercial_tiers,
    calculate_de_international_fee,
    DE_FVF_CAP_CONFIGURED,
)


@pytest.fixture
def calc():
    return ProfitCalculator()


def _de_input(**kwargs):
    defaults = {
        "marketplace": "DE",
        "currency": "EUR",
        "de_seller_type": DESellerType.COMMERCIAL,
        "seller_level": SellerLevel.ABOVE_STANDARD,
    }
    defaults.update(kwargs)
    return ProfitInput(**defaults)


# =============================================================================
# TIERED FEE CALCULATION
# =============================================================================

class TestTieredFee:
    def test_single_tier(self):
        tiers = [FeeTier(None, 0.11)]
        fee = calculate_tiered_fee(Decimal("100"), tiers)
        assert fee == Decimal("11")

    def test_two_tiers_below_threshold(self):
        tiers = [FeeTier(990, 0.11), FeeTier(None, 0.02)]
        fee = calculate_tiered_fee(Decimal("500"), tiers)
        expected = Decimal("500") * Decimal("0.11")
        assert abs(fee - expected) < Decimal("0.01")

    def test_two_tiers_above_threshold(self):
        tiers = [FeeTier(990, 0.11), FeeTier(None, 0.02)]
        fee = calculate_tiered_fee(Decimal("1500"), tiers)
        expected = (
            Decimal("990") * Decimal("0.11")
            + Decimal("510") * Decimal("0.02")
        )
        assert abs(fee - expected) < Decimal("0.01")

    def test_exactly_at_threshold(self):
        tiers = [FeeTier(200, 0.065), FeeTier(None, 0.02)]
        fee = calculate_tiered_fee(Decimal("200"), tiers)
        expected = Decimal("200") * Decimal("0.065")
        assert abs(fee - expected) < Decimal("0.01")

    def test_200_threshold(self):
        tiers = [FeeTier(200, 0.065), FeeTier(None, 0.02)]
        fee = calculate_tiered_fee(Decimal("500"), tiers)
        expected = (
            Decimal("200") * Decimal("0.065")
            + Decimal("300") * Decimal("0.02")
        )
        assert abs(fee - expected) < Decimal("0.01")

    def test_300_threshold(self):
        tiers = [FeeTier(300, 0.11), FeeTier(None, 0.02)]
        fee = calculate_tiered_fee(Decimal("500"), tiers)
        expected = (
            Decimal("300") * Decimal("0.11")
            + Decimal("200") * Decimal("0.02")
        )
        assert abs(fee - expected) < Decimal("0.01")

    def test_400_threshold(self):
        tiers = [FeeTier(400, 0.14), FeeTier(None, 0.02)]
        fee = calculate_tiered_fee(Decimal("600"), tiers)
        expected = (
            Decimal("400") * Decimal("0.14")
            + Decimal("200") * Decimal("0.02")
        )
        assert abs(fee - expected) < Decimal("0.01")

    def test_1990_threshold(self):
        tiers = [FeeTier(1990, 0.11), FeeTier(None, 0.02)]
        fee = calculate_tiered_fee(Decimal("2500"), tiers)
        expected = (
            Decimal("1990") * Decimal("0.11")
            + Decimal("510") * Decimal("0.02")
        )
        assert abs(fee - expected) < Decimal("0.01")

    def test_zero_amount(self):
        tiers = [FeeTier(990, 0.11), FeeTier(None, 0.02)]
        assert calculate_tiered_fee(Decimal("0"), tiers) == Decimal("0")

    def test_very_high_price(self):
        tiers = [FeeTier(990, 0.11), FeeTier(None, 0.02)]
        fee = calculate_tiered_fee(Decimal("10000"), tiers)
        expected = (
            Decimal("990") * Decimal("0.11")
            + Decimal("9010") * Decimal("0.02")
        )
        assert abs(fee - expected) < Decimal("0.01")


# =============================================================================
# EXCLUDED CATEGORIES
# =============================================================================

class TestExcludedCategories:
    def test_motors_excluded(self):
        assert is_excluded_category("motors")

    def test_real_estate_excluded(self):
        assert is_excluded_category("real_estate")

    def test_classified_ads_excluded(self):
        assert is_excluded_category("classified_ads")

    def test_electronics_not_excluded(self):
        assert not is_excluded_category("computers")

    def test_excluded_returns_warning(self, calc):
        inputs = _de_input(
            sold_price=Decimal("1000"),
            item_cost=Decimal("500"),
            category="motors",
        )
        result = calc.calculate(inputs)
        assert any("excluded" in w.lower() for w in result.warnings)
        assert result.confidence == "low"


# =============================================================================
# PRIVATE SELLER FVF
# =============================================================================

class TestPrivateSellerFVF:
    def test_eurozone_sweden_zero(self, calc):
        inputs = _de_input(
            de_seller_type=DESellerType.PRIVATE,
            de_buyer_region=DEBuyerRegion.EUROZONE_SWEDEN,
            sold_price=Decimal("2500"),
            item_cost=Decimal("100"),
            overseas_sales=True,
        )
        result = calc.calculate(inputs)
        assert result.fees.fvf == Decimal("0")

    def test_other_region_progressive(self, calc):
        """Private, Other region: 11% up to €1,990 + 2% above."""
        inputs = _de_input(
            de_seller_type=DESellerType.PRIVATE,
            de_buyer_region=DEBuyerRegion.OTHER,
            sold_price=Decimal("2500"),
            shipping_charged=Decimal("0"),
            item_cost=Decimal("100"),
            overseas_sales=True,
        )
        result = calc.calculate(inputs)
        # FVF = 1990 * 0.11 + 510 * 0.02 = 218.90 + 10.20 = 229.10
        expected_fvf = (
            Decimal("1990") * Decimal("0.11")
            + Decimal("510") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected_fvf) < Decimal("0.01")

    def test_other_region_below_threshold(self, calc):
        inputs = _de_input(
            de_seller_type=DESellerType.PRIVATE,
            de_buyer_region=DEBuyerRegion.EUROPE_USA_CANADA,
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            overseas_sales=True,
        )
        result = calc.calculate(inputs)
        expected = Decimal("500") * Decimal("0.11")
        assert abs(result.fees.fvf - expected) < Decimal("0.01")


# =============================================================================
# COMMERCIAL SELLER FVF — SHOP VARIATION
# =============================================================================

class TestCommercialShopVariation:
    def test_domestic_appliances_with_shop(self, calc):
        """Domestic appliances + Shop: 200/6.5% + 2%."""
        inputs = _de_input(
            de_seller_type=DESellerType.COMMERCIAL,
            ebay_shop=True,
            sold_price=Decimal("500"),
            shipping_charged=Decimal("20"),
            item_cost=Decimal("100"),
            shipping_cost=Decimal("20"),
            category="domestic_appliances",
        )
        result = calc.calculate(inputs)
        # FVF base = 520. 200*0.065 + 320*0.02 = 13 + 6.40 = 19.40
        expected = (
            Decimal("200") * Decimal("0.065")
            + Decimal("320") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_domestic_appliances_no_shop(self, calc):
        """Domestic appliances + No Shop: 990/6.5% + 2%."""
        inputs = _de_input(
            de_seller_type=DESellerType.COMMERCIAL,
            ebay_shop=False,
            sold_price=Decimal("500"),
            shipping_charged=Decimal("20"),
            item_cost=Decimal("100"),
            category="domestic_appliances",
        )
        result = calc.calculate(inputs)
        # FVF base = 520. All under 990 → 520*0.065 = 33.80
        expected = Decimal("520") * Decimal("0.065")
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_musical_instruments_with_shop(self, calc):
        inputs = _de_input(
            de_seller_type=DESellerType.COMMERCIAL,
            ebay_shop=True,
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            category="musical_instruments",
        )
        result = calc.calculate(inputs)
        # 300*0.11 + 200*0.02 = 33 + 4 = 37
        expected = (
            Decimal("300") * Decimal("0.11")
            + Decimal("200") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected) < Decimal("0.01")


# =============================================================================
# COMMERCIAL CATEGORIES
# =============================================================================

class TestCommercialCategories:
    def test_clothing_accessories(self, calc):
        inputs = _de_input(
            sold_price=Decimal("1200"),
            item_cost=Decimal("200"),
            category="clothing_accessories",
        )
        result = calc.calculate(inputs)
        # 990*0.12 + 210*0.02 = 118.80 + 4.20 = 123.00
        expected = (
            Decimal("990") * Decimal("0.12")
            + Decimal("210") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_garden_handyman(self, calc):
        inputs = _de_input(
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            category="garden_handyman",
        )
        result = calc.calculate(inputs)
        # 200*0.12 + 300*0.02 = 24 + 6 = 30
        expected = (
            Decimal("200") * Decimal("0.12")
            + Decimal("300") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_tickets(self, calc):
        inputs = _de_input(
            sold_price=Decimal("1200"),
            item_cost=Decimal("200"),
            category="tickets",
        )
        result = calc.calculate(inputs)
        # 990*0.09 + 210*0.02 = 89.10 + 4.20 = 93.30
        expected = (
            Decimal("990") * Decimal("0.09")
            + Decimal("210") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_general_fallback(self, calc):
        inputs = _de_input(
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            category="books",
        )
        result = calc.calculate(inputs)
        # Falls to general: 500*0.11 = 55
        expected = Decimal("500") * Decimal("0.11")
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_unknown_category_uses_general(self, calc):
        inputs = _de_input(
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            category="something_completely_unknown",
        )
        result = calc.calculate(inputs)
        expected = Decimal("500") * Decimal("0.11")
        assert abs(result.fees.fvf - expected) < Decimal("0.01")


# =============================================================================
# SUBCATEGORIES
# =============================================================================

class TestSubcategories:
    def test_automotive_specified_electronics_shop(self, calc):
        inputs = _de_input(
            ebay_shop=True,
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            category="automotive_parts",
            subcategory="specified_electronics",
        )
        result = calc.calculate(inputs)
        # 300*0.065 + 200*0.02 = 19.50 + 4 = 23.50
        expected = (
            Decimal("300") * Decimal("0.065")
            + Decimal("200") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_automotive_chargers_no_shop(self, calc):
        inputs = _de_input(
            ebay_shop=False,
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            category="automotive_parts",
            subcategory="chargers_wall_boxes",
        )
        result = calc.calculate(inputs)
        # No shop: 990/6.5% → 500*0.065 = 32.50
        expected = Decimal("500") * Decimal("0.065")
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_beauty_electric_hair_shop(self, calc):
        inputs = _de_input(
            ebay_shop=True,
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            category="beauty",
            subcategory="electric_hair_dental",
        )
        result = calc.calculate(inputs)
        # Shop: 300*0.065 + 200*0.02 = 19.50 + 4 = 23.50
        expected = (
            Decimal("300") * Decimal("0.065")
            + Decimal("200") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_computers_printers_shop(self, calc):
        inputs = _de_input(
            ebay_shop=True,
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            category="computers",
            subcategory="printers_scanners",
        )
        result = calc.calculate(inputs)
        # Shop: 200*0.065 + 300*0.02 = 13 + 6 = 19
        expected = (
            Decimal("200") * Decimal("0.065")
            + Decimal("300") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_watches_specified_shop(self, calc):
        inputs = _de_input(
            ebay_shop=True,
            sold_price=Decimal("600"),
            item_cost=Decimal("100"),
            category="watches_jewellery",
            subcategory="watches_specified",
        )
        result = calc.calculate(inputs)
        # Shop: 400*0.11 + 200*0.02 = 44 + 4 = 48
        expected = (
            Decimal("400") * Decimal("0.11")
            + Decimal("200") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_watches_default_shop(self, calc):
        inputs = _de_input(
            ebay_shop=True,
            sold_price=Decimal("600"),
            item_cost=Decimal("100"),
            category="watches_jewellery",
        )
        result = calc.calculate(inputs)
        # Default: 400*0.14 + 200*0.02 = 56 + 4 = 60
        expected = (
            Decimal("400") * Decimal("0.14")
            + Decimal("200") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_nft_antiques(self, calc):
        inputs = _de_input(
            sold_price=Decimal("1000"),
            item_cost=Decimal("200"),
            category="antiques_art",
            subcategory="nft",
        )
        result = calc.calculate(inputs)
        # NFT: flat 5%
        expected = Decimal("1000") * Decimal("0.05")
        assert abs(result.fees.fvf - expected) < Decimal("0.01")

    def test_nft_toys(self, calc):
        inputs = _de_input(
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            category="toys_hobbies",
            subcategory="nft",
        )
        result = calc.calculate(inputs)
        expected = Decimal("500") * Decimal("0.05")
        assert abs(result.fees.fvf - expected) < Decimal("0.01")


# =============================================================================
# INTERNATIONAL FEES
# =============================================================================

class TestDEInternational:
    def test_no_overseas(self, calc):
        inputs = _de_input(
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            overseas_sales=False,
        )
        result = calc.calculate(inputs)
        assert result.fees.international_fee == Decimal("0")

    def test_private_eurozone(self):
        fee = calculate_de_international_fee(
            Decimal("100"), "private", "eurozone_sweden", True
        )
        assert fee == Decimal("0")

    def test_private_europe_usa_canada(self):
        fee = calculate_de_international_fee(
            Decimal("100"), "private", "europe_usa_canada", True
        )
        assert abs(fee - Decimal("1.91")) < Decimal("0.01")

    def test_private_uk(self):
        fee = calculate_de_international_fee(
            Decimal("100"), "private", "uk", True
        )
        assert abs(fee - Decimal("1.43")) < Decimal("0.01")

    def test_private_other(self):
        fee = calculate_de_international_fee(
            Decimal("100"), "private", "other", True
        )
        assert abs(fee - Decimal("3.93")) < Decimal("0.01")

    def test_commercial_eurozone(self):
        fee = calculate_de_international_fee(
            Decimal("100"), "commercial", "eurozone_sweden", True
        )
        assert fee == Decimal("0")

    def test_commercial_europe_usa_canada(self):
        fee = calculate_de_international_fee(
            Decimal("100"), "commercial", "europe_usa_canada", True
        )
        assert abs(fee - Decimal("1.60")) < Decimal("0.01")

    def test_commercial_uk(self):
        fee = calculate_de_international_fee(
            Decimal("100"), "commercial", "uk", True
        )
        assert abs(fee - Decimal("1.20")) < Decimal("0.01")

    def test_commercial_other(self):
        fee = calculate_de_international_fee(
            Decimal("100"), "commercial", "other", True
        )
        assert abs(fee - Decimal("3.30")) < Decimal("0.01")


# =============================================================================
# VAT HANDLING
# =============================================================================

class TestDEVAT:
    def test_vat_inclusive_no_double_count(self, calc):
        inputs = _de_input(
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            category="domestic_appliances",
        )
        result = calc.calculate(inputs)
        # VAT on fees should be 0 (already included)
        assert result.fees.vat_on_fees == Decimal("0")
        assert any("19% VAT" in a for a in result.assumptions)
        assert any("VAT-inclusive" in a for a in result.assumptions)


# =============================================================================
# FVF CAP WARNING
# =============================================================================

class TestFVFCap:
    def test_cap_warning_present(self, calc):
        inputs = _de_input(
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
        )
        result = calc.calculate(inputs)
        assert any("cap" in w.lower() for w in result.warnings)
        assert not DE_FVF_CAP_CONFIGURED


# =============================================================================
# PROFIT CALCULATIONS
# =============================================================================

class TestDEProfit:
    def test_positive_profit(self, calc):
        inputs = _de_input(
            sold_price=Decimal("500"),
            shipping_charged=Decimal("20"),
            item_cost=Decimal("100"),
            shipping_cost=Decimal("20"),
            category="domestic_appliances",
            ebay_shop=True,
        )
        result = calc.calculate(inputs)
        assert result.is_profitable
        assert result.net_profit_per_item > 0
        assert result.profit_margin > 0

    def test_negative_profit(self, calc):
        inputs = _de_input(
            sold_price=Decimal("50"),
            item_cost=Decimal("200"),
            shipping_cost=Decimal("50"),
        )
        result = calc.calculate(inputs)
        assert not result.is_profitable
        assert result.net_profit_per_item < 0

    def test_roi(self, calc):
        inputs = _de_input(
            sold_price=Decimal("500"),
            item_cost=Decimal("100"),
            shipping_cost=Decimal("20"),
            category="general",
        )
        result = calc.calculate(inputs)
        assert result.roi > 0

    def test_effective_percentages(self, calc):
        inputs = _de_input(
            sold_price=Decimal("500"),
            shipping_charged=Decimal("20"),
            item_cost=Decimal("100"),
            shipping_cost=Decimal("20"),
        )
        result = calc.calculate(inputs)
        assert result.fees.fvf_pct > 0
        assert result.fees.total_fees_pct > 0


# =============================================================================
# FULL SCENARIO (from spec)
# =============================================================================

class TestDEFullScenario:
    def test_supplied_example(self, calc):
        """
        Commercial, Shop, Domestic appliances, €500 + €20 shipping,
        Cost €100 + €20 shipping, Overseas Europe/USA/Canada.
        """
        inputs = _de_input(
            de_seller_type=DESellerType.COMMERCIAL,
            ebay_shop=True,
            sold_price=Decimal("500"),
            shipping_charged=Decimal("20"),
            item_cost=Decimal("100"),
            shipping_cost=Decimal("20"),
            num_orders=1,
            category="domestic_appliances",
            overseas_sales=True,
            de_buyer_region=DEBuyerRegion.EUROPE_USA_CANADA,
        )
        result = calc.calculate(inputs)

        assert result.marketplace == "DE"
        assert result.currency == "EUR"

        # FVF: 200*0.065 + 320*0.02 = 19.40
        expected_fvf = (
            Decimal("200") * Decimal("0.065")
            + Decimal("320") * Decimal("0.02")
        )
        assert abs(result.fees.fvf - expected_fvf) < Decimal("0.01")

        # International: 520 * 1.60% = 8.32
        expected_intl = Decimal("520") * Decimal("0.016")
        assert abs(result.fees.international_fee - expected_intl) < Decimal("0.01")

        assert result.fees.vat_on_fees == Decimal("0")
        assert result.num_orders == 1
        assert len(result.assumptions) > 0

    def test_result_to_dict(self, calc):
        inputs = _de_input(
            sold_price=Decimal("100"),
            item_cost=Decimal("20"),
        )
        result = calc.calculate(inputs)
        d = result.to_dict()
        assert d["marketplace"] == "DE"
        assert d["currency"] == "EUR"
        assert "ebay_shop" in d
        assert "variable_fvf" in d["fees"]


# =============================================================================
# REGRESSION — US AND UK UNAFFECTED
# =============================================================================

class TestRegression:
    def test_us_still_works(self, calc):
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

    def test_uk_still_works(self, calc):
        inputs = ProfitInput(
            marketplace="UK",
            currency="GBP",
            uk_seller_type=UKSellerType.BUSINESS,
            sold_price=Decimal("100"),
            item_cost=Decimal("10"),
        )
        result = calc.calculate(inputs)
        assert result.marketplace == "UK"
        assert result.currency == "GBP"
        assert result.fees.fvf > 0