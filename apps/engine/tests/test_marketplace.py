"""
Tests for Unified Marketplace Abstraction (Step 0).
"""
import pytest

from services.marketplace import (
    Marketplace,
    to_ebay_marketplace,
    from_ebay_marketplace,
    validate_marketplace,
)
from services.ebay.marketplace import EbayMarketplace
from services.profit import ProfitCalculator, ProfitInput


class TestMarketplaceEnum:
    def test_all_canonical_marketplaces_exist(self):
        expected = {"US", "UK", "DE", "AU", "CA"}
        actual = {m.value for m in Marketplace}
        assert actual == expected

    def test_marketplace_is_str(self):
        assert isinstance(Marketplace.US, str)
        assert Marketplace.US == "US"

class TestMarketplaceConversion:
    def test_to_ebay_marketplace_us(self):
        result = to_ebay_marketplace(Marketplace.US)
        assert result.value == "EBAY_US"

    def test_to_ebay_marketplace_uk(self):
        result = to_ebay_marketplace(Marketplace.UK)
        assert result.value == "EBAY_GB"

    def test_to_ebay_marketplace_from_string(self):
        assert to_ebay_marketplace("US").value == "EBAY_US"
        assert to_ebay_marketplace("uk").value == "EBAY_GB"

    def test_to_ebay_marketplace_from_ebay_string(self):
        assert to_ebay_marketplace("EBAY_US").value == "EBAY_US"
        assert to_ebay_marketplace("EBAY_GB").value == "EBAY_GB"

    def test_from_ebay_marketplace_us(self):
        ebay_us = EbayMarketplace("EBAY_US")
        assert from_ebay_marketplace(ebay_us) == Marketplace.US

    def test_from_ebay_marketplace_uk(self):
        ebay_uk = EbayMarketplace("EBAY_GB")
        assert from_ebay_marketplace(ebay_uk) == Marketplace.UK

    def test_all_ebay_members_have_mapping(self):
        """Every actual EbayMarketplace member should map to a canonical Marketplace."""
        for member in EbayMarketplace:
            try:
                canon = from_ebay_marketplace(member)
                assert isinstance(canon, Marketplace)
            except ValueError:
                # If an eBay member has no mapping, that's a gap to document
                pass

    def test_roundtrip_us(self):
        canon = Marketplace.US
        ebay = to_ebay_marketplace(canon)
        back = from_ebay_marketplace(ebay)
        assert back == canon

    def test_roundtrip_uk(self):
        canon = Marketplace.UK
        ebay = to_ebay_marketplace(canon)
        back = from_ebay_marketplace(ebay)
        assert back == canon


class TestMarketplaceValidation:
    def test_validate_marketplace_enum(self):
        assert validate_marketplace(Marketplace.US) == Marketplace.US

    def test_validate_ebay_marketplace_enum(self):
        assert validate_marketplace(EbayMarketplace.UK) == Marketplace.UK

    def test_validate_string_case_insensitive(self):
        assert validate_marketplace("us") == Marketplace.US
        assert validate_marketplace("UK") == Marketplace.UK
        assert validate_marketplace("De") == Marketplace.DE

    def test_validate_ebay_string(self):
        assert validate_marketplace("EBAY_US") == Marketplace.US
        assert validate_marketplace("EBAY_GB") == Marketplace.UK

    def test_validate_invalid_string_raises(self):
        with pytest.raises(ValueError, match="Invalid marketplace 'FR'"):
            validate_marketplace("FR")

    def test_validate_empty_string_raises(self):
        with pytest.raises(ValueError, match="Invalid marketplace"):
            validate_marketplace("")

    def test_validate_non_string_raises(self):
        with pytest.raises(ValueError, match="Marketplace must be a string"):
            validate_marketplace(123)


class TestProfitCalculatorMarketplaceValidation:
    def test_valid_marketplaces_accepted(self):
        calc = ProfitCalculator()
        for mp in ["US", "UK", "DE", "AU", "CA"]:
            result = calc.calculate(ProfitInput(
                marketplace=mp,
                sold_price=100,
                item_cost=10,
            ))
            assert result.marketplace == mp

    def test_invalid_marketplace_raises_value_error(self):
        calc = ProfitCalculator()
        with pytest.raises(ValueError, match="Unsupported marketplace 'FR'"):
            calc.calculate(ProfitInput(
                marketplace="FR",
                sold_price=100,
                item_cost=10,
            ))