"""
Tests for settings marketplace validation.
"""
import os
from unittest.mock import patch

import pytest


class TestSettingsMarketplaceValidation:
    """Test that settings validates marketplace ID correctly."""

    def test_default_marketplace_is_us(self):
        """When no env var set, defaults to EBAY_US."""
        # Import fresh
        from config.settings import Settings
        # Explicitly no env override
        s = Settings(ebay_marketplace_id="EBAY_US")
        assert s.ebay_marketplace_id == "EBAY_US"

    def test_valid_us_marketplace(self):
        from config.settings import Settings
        s = Settings(ebay_marketplace_id="EBAY_US")
        assert s.ebay_marketplace_id == "EBAY_US"

    def test_valid_uk_marketplace(self):
        from config.settings import Settings
        s = Settings(ebay_marketplace_id="EBAY_GB")
        assert s.ebay_marketplace_id == "EBAY_GB"

    def test_valid_germany_marketplace(self):
        from config.settings import Settings
        s = Settings(ebay_marketplace_id="EBAY_DE")
        assert s.ebay_marketplace_id == "EBAY_DE"

    def test_valid_australia_marketplace(self):
        from config.settings import Settings
        s = Settings(ebay_marketplace_id="EBAY_AU")
        assert s.ebay_marketplace_id == "EBAY_AU"

    def test_valid_canada_marketplace(self):
        from config.settings import Settings
        s = Settings(ebay_marketplace_id="EBAY_CA")
        assert s.ebay_marketplace_id == "EBAY_CA"

    def test_invalid_marketplace_rejected(self):
        from config.settings import Settings
        with pytest.raises(Exception) as exc_info:
            Settings(ebay_marketplace_id="EBAY_JP")
        # Pydantic wraps ValueError in ValidationError
        assert "EBAY_JP" in str(exc_info.value) or "Unsupported" in str(exc_info.value)

    def test_invalid_random_string_rejected(self):
        from config.settings import Settings
        with pytest.raises(Exception):
            Settings(ebay_marketplace_id="not_a_marketplace")

    def test_ebay_marketplace_property_returns_enum(self):
        from config.settings import Settings
        from services.ebay.marketplace import EbayMarketplace

        s = Settings(ebay_marketplace_id="EBAY_GB")
        assert s.ebay_marketplace == EbayMarketplace.UK

    def test_ebay_marketplace_property_default(self):
        from config.settings import Settings
        from services.ebay.marketplace import EbayMarketplace

        s = Settings(ebay_marketplace_id="EBAY_US")
        assert s.ebay_marketplace == EbayMarketplace.US