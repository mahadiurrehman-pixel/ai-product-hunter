"""
Tests for EbayMarketplace enum and metadata.
"""
import pytest

from services.ebay.marketplace import EbayMarketplace, MarketplaceMetadata


class TestEbayMarketplaceEnum:
    """Test EbayMarketplace enum members."""

    def test_us_marketplace_value(self):
        assert EbayMarketplace.US.value == "EBAY_US"

    def test_uk_marketplace_value(self):
        assert EbayMarketplace.UK.value == "EBAY_GB"

    def test_germany_marketplace_value(self):
        assert EbayMarketplace.GERMANY.value == "EBAY_DE"

    def test_australia_marketplace_value(self):
        assert EbayMarketplace.AUSTRALIA.value == "EBAY_AU"

    def test_canada_marketplace_value(self):
        assert EbayMarketplace.CANADA.value == "EBAY_CA"

    def test_exactly_five_marketplaces_supported(self):
        """Exactly the 5 required marketplaces exist."""
        expected = {"EBAY_US", "EBAY_GB", "EBAY_DE", "EBAY_AU", "EBAY_CA"}
        actual = {m.value for m in EbayMarketplace}
        assert actual == expected

    def test_enum_is_string_type(self):
        """Enum members behave as strings for direct header usage."""
        assert isinstance(EbayMarketplace.US, str)
        assert EbayMarketplace.US == "EBAY_US"


class TestEbayMarketplaceMetadata:
    """Test marketplace metadata properties."""

    def test_us_display_name(self):
        assert EbayMarketplace.US.display_name == "eBay United States"

    def test_uk_display_name(self):
        assert EbayMarketplace.UK.display_name == "eBay United Kingdom"

    def test_germany_display_name(self):
        assert EbayMarketplace.GERMANY.display_name == "eBay Germany"

    def test_australia_display_name(self):
        assert EbayMarketplace.AUSTRALIA.display_name == "eBay Australia"

    def test_canada_display_name(self):
        assert EbayMarketplace.CANADA.display_name == "eBay Canada"

    def test_us_currency(self):
        assert EbayMarketplace.US.currency == "USD"

    def test_uk_currency(self):
        assert EbayMarketplace.UK.currency == "GBP"

    def test_germany_currency(self):
        assert EbayMarketplace.GERMANY.currency == "EUR"

    def test_australia_currency(self):
        assert EbayMarketplace.AUSTRALIA.currency == "AUD"

    def test_canada_currency(self):
        assert EbayMarketplace.CANADA.currency == "CAD"

    def test_us_region(self):
        assert EbayMarketplace.US.region == "United States"

    def test_all_marketplaces_have_metadata(self):
        """Every enum member has complete metadata."""
        for marketplace in EbayMarketplace:
            metadata = marketplace.metadata
            assert isinstance(metadata, MarketplaceMetadata)
            assert metadata.display_name != ""
            assert len(metadata.currency) == 3  # ISO 4217
            assert metadata.region != ""


class TestEbayMarketplaceFromId:
    """Test from_id parsing method."""

    def test_from_id_us(self):
        assert EbayMarketplace.from_id("EBAY_US") == EbayMarketplace.US

    def test_from_id_uk(self):
        assert EbayMarketplace.from_id("EBAY_GB") == EbayMarketplace.UK

    def test_from_id_germany(self):
        assert EbayMarketplace.from_id("EBAY_DE") == EbayMarketplace.GERMANY

    def test_from_id_australia(self):
        assert EbayMarketplace.from_id("EBAY_AU") == EbayMarketplace.AUSTRALIA

    def test_from_id_canada(self):
        assert EbayMarketplace.from_id("EBAY_CA") == EbayMarketplace.CANADA

    def test_from_id_case_insensitive(self):
        assert EbayMarketplace.from_id("ebay_us") == EbayMarketplace.US
        assert EbayMarketplace.from_id("Ebay_De") == EbayMarketplace.GERMANY

    def test_from_id_strips_whitespace(self):
        assert EbayMarketplace.from_id("  EBAY_US  ") == EbayMarketplace.US

    def test_from_id_invalid_raises(self):
        with pytest.raises(ValueError) as exc_info:
            EbayMarketplace.from_id("EBAY_JP")
        assert "Unsupported" in str(exc_info.value)
        assert "EBAY_JP" in str(exc_info.value)

    def test_from_id_empty_raises(self):
        with pytest.raises(ValueError):
            EbayMarketplace.from_id("")

    def test_from_id_none_raises(self):
        with pytest.raises((ValueError, TypeError, AttributeError)):
            EbayMarketplace.from_id(None)

    def test_from_id_random_string_raises(self):
        with pytest.raises(ValueError):
            EbayMarketplace.from_id("not_a_marketplace")


class TestEbayMarketplaceHelpers:
    """Test helper methods on EbayMarketplace."""

    def test_supported_ids_returns_all_five(self):
        ids = EbayMarketplace.supported_ids()
        assert len(ids) == 5
        assert "EBAY_US" in ids
        assert "EBAY_GB" in ids
        assert "EBAY_DE" in ids
        assert "EBAY_AU" in ids
        assert "EBAY_CA" in ids

    def test_all_metadata_returns_five_entries(self):
        metadata = EbayMarketplace.all_metadata()
        assert len(metadata) == 5

    def test_all_metadata_has_required_keys(self):
        for entry in EbayMarketplace.all_metadata():
            assert "id" in entry
            assert "display_name" in entry
            assert "currency" in entry
            assert "region" in entry

    def test_all_metadata_us_entry(self):
        metadata = EbayMarketplace.all_metadata()
        us = next(e for e in metadata if e["id"] == "EBAY_US")
        assert us["display_name"] == "eBay United States"
        assert us["currency"] == "USD"
        assert us["region"] == "United States"

    def test_all_metadata_useful_for_ui(self):
        """all_metadata provides everything needed for UI dropdowns."""
        metadata = EbayMarketplace.all_metadata()
        # Should be able to build dropdown from this
        for entry in metadata:
            display_string = f"{entry['display_name']} ({entry['currency']})"
            assert entry["id"] in EbayMarketplace.supported_ids()
            assert len(display_string) > 0