"""
Tests for EbayListingRepository marketplace-aware persistence.
"""
from datetime import datetime
from decimal import Decimal

import pytest

from services.ebay.repository import EbayListingRepository
from models.ebay import EbayListing


class TestRepositoryMarketplacePersistence:
    """Test marketplace field is correctly persisted."""

    def _base_listing_data(self, item_id="v1|123|0", marketplace="EBAY_US"):
        return {
            "item_id": item_id,
            "marketplace": marketplace,
            "title": f"Test Product {item_id}",
            "price_value": Decimal("29.99"),
            "price_currency": "USD",
            "item_web_url": f"https://ebay.com/itm/{item_id}",
            "raw_data": {},
            "fetched_at": datetime.utcnow(),
        }

    def test_save_us_listing_stores_marketplace(self, db_session):
        data = self._base_listing_data(marketplace="EBAY_US")
        listing = EbayListingRepository.save_listing(db_session, data)
        assert listing.marketplace == "EBAY_US"

    def test_save_uk_listing_stores_marketplace(self, db_session):
        data = self._base_listing_data(marketplace="EBAY_GB")
        data["price_currency"] = "GBP"
        listing = EbayListingRepository.save_listing(db_session, data)
        assert listing.marketplace == "EBAY_GB"

    def test_save_germany_listing_stores_marketplace(self, db_session):
        data = self._base_listing_data(marketplace="EBAY_DE")
        data["price_currency"] = "EUR"
        listing = EbayListingRepository.save_listing(db_session, data)
        assert listing.marketplace == "EBAY_DE"

    def test_save_australia_listing_stores_marketplace(self, db_session):
        data = self._base_listing_data(marketplace="EBAY_AU")
        data["price_currency"] = "AUD"
        listing = EbayListingRepository.save_listing(db_session, data)
        assert listing.marketplace == "EBAY_AU"

    def test_save_canada_listing_stores_marketplace(self, db_session):
        data = self._base_listing_data(marketplace="EBAY_CA")
        data["price_currency"] = "CAD"
        listing = EbayListingRepository.save_listing(db_session, data)
        assert listing.marketplace == "EBAY_CA"

    def test_save_without_marketplace_defaults_to_us(self, db_session):
        """Backward compatibility: missing marketplace defaults to EBAY_US."""
        data = self._base_listing_data()
        del data["marketplace"]  # simulate old code without marketplace
        listing = EbayListingRepository.save_listing(db_session, data)
        assert listing.marketplace == "EBAY_US"


class TestRepositoryMarketplaceIsolation:
    """Test that same item_id from different marketplaces coexists."""

    def _base_listing_data(self, item_id, marketplace, currency="USD"):
        return {
            "item_id": item_id,
            "marketplace": marketplace,
            "title": f"Product {item_id} on {marketplace}",
            "price_value": Decimal("29.99"),
            "price_currency": currency,
            "item_web_url": f"https://ebay.com/itm/{item_id}",
            "raw_data": {},
            "fetched_at": datetime.utcnow(),
        }

    def test_same_item_id_different_marketplaces_coexist(self, db_session):
        """Same item_id can exist on EBAY_US and EBAY_DE without collision."""
        us_data = self._base_listing_data(
            "v1|shared_id|0", "EBAY_US", "USD"
        )
        de_data = self._base_listing_data(
            "v1|shared_id|0", "EBAY_DE", "EUR"
        )

        us_listing = EbayListingRepository.save_listing(db_session, us_data)
        de_listing = EbayListingRepository.save_listing(db_session, de_data)

        # Both should exist as separate records
        assert us_listing.id != de_listing.id
        assert us_listing.marketplace == "EBAY_US"
        assert de_listing.marketplace == "EBAY_DE"

        # Verify both retrievable
        all_records = (
            db_session.query(EbayListing)
            .filter(EbayListing.item_id == "v1|shared_id|0")
            .all()
        )
        assert len(all_records) == 2
        marketplaces = {r.marketplace for r in all_records}
        assert marketplaces == {"EBAY_US", "EBAY_DE"}

    def test_upsert_same_marketplace_same_item_updates(self, db_session):
        """Same (marketplace, item_id) upserts, doesn't create duplicate."""
        data = self._base_listing_data(
            "v1|upsert_test|0", "EBAY_US", "USD"
        )
        first = EbayListingRepository.save_listing(db_session, data)
        first_id = first.id

        # Update
        data["title"] = "Updated Title"
        data["price_value"] = Decimal("39.99")
        second = EbayListingRepository.save_listing(db_session, data)

        assert second.id == first_id
        assert second.title == "Updated Title"

    def test_five_marketplaces_same_item_id(self, db_session):
        """Same item_id can exist on all 5 marketplaces simultaneously."""
        marketplaces = [
            ("EBAY_US", "USD"),
            ("EBAY_GB", "GBP"),
            ("EBAY_DE", "EUR"),
            ("EBAY_AU", "AUD"),
            ("EBAY_CA", "CAD"),
        ]

        for mp, currency in marketplaces:
            data = self._base_listing_data(
                "v1|multi_market|0", mp, currency
            )
            EbayListingRepository.save_listing(db_session, data)

        all_records = (
            db_session.query(EbayListing)
            .filter(EbayListing.item_id == "v1|multi_market|0")
            .all()
        )
        assert len(all_records) == 5


class TestRepositoryLookupWithMarketplace:
    """Test lookup methods with marketplace parameter."""

    def _base_listing_data(self, item_id, marketplace):
        return {
            "item_id": item_id,
            "marketplace": marketplace,
            "title": "Test",
            "price_value": Decimal("10.00"),
            "price_currency": "USD",
            "item_web_url": "https://ebay.com/itm/x",
            "raw_data": {},
            "fetched_at": datetime.utcnow(),
        }

    def test_get_by_marketplace_and_item_found(self, db_session):
        data = self._base_listing_data("v1|find|0", "EBAY_GB")
        EbayListingRepository.save_listing(db_session, data)

        found = EbayListingRepository.get_by_marketplace_and_item(
            db_session, "EBAY_GB", "v1|find|0"
        )
        assert found is not None
        assert found.marketplace == "EBAY_GB"

    def test_get_by_marketplace_and_item_wrong_marketplace(self, db_session):
        data = self._base_listing_data("v1|find|0", "EBAY_GB")
        EbayListingRepository.save_listing(db_session, data)

        # Looking for same item on different marketplace — should not find
        found = EbayListingRepository.get_by_marketplace_and_item(
            db_session, "EBAY_US", "v1|find|0"
        )
        assert found is None

    def test_get_by_item_id_with_marketplace_filter(self, db_session):
        data_us = self._base_listing_data("v1|dual|0", "EBAY_US")
        data_de = self._base_listing_data("v1|dual|0", "EBAY_DE")
        EbayListingRepository.save_listing(db_session, data_us)
        EbayListingRepository.save_listing(db_session, data_de)

        us_result = EbayListingRepository.get_by_item_id(
            db_session, "v1|dual|0", marketplace="EBAY_US"
        )
        de_result = EbayListingRepository.get_by_item_id(
            db_session, "v1|dual|0", marketplace="EBAY_DE"
        )

        assert us_result is not None
        assert us_result.marketplace == "EBAY_US"
        assert de_result is not None
        assert de_result.marketplace == "EBAY_DE"

    def test_get_by_item_id_without_marketplace_backward_compat(
        self, db_session
    ):
        """Without marketplace filter, returns first match (legacy behavior)."""
        data = self._base_listing_data("v1|legacy|0", "EBAY_US")
        EbayListingRepository.save_listing(db_session, data)

        # Call without marketplace — should still work
        found = EbayListingRepository.get_by_item_id(
            db_session, "v1|legacy|0"
        )
        assert found is not None

    def test_get_recent_listings_with_marketplace_filter(self, db_session):
        data_us = self._base_listing_data("v1|recent_us|0", "EBAY_US")
        data_de = self._base_listing_data("v1|recent_de|0", "EBAY_DE")
        EbayListingRepository.save_listing(db_session, data_us)
        EbayListingRepository.save_listing(db_session, data_de)

        us_recent = EbayListingRepository.get_recent_listings(
            db_session, marketplace="EBAY_US"
        )
        de_recent = EbayListingRepository.get_recent_listings(
            db_session, marketplace="EBAY_DE"
        )

        us_marketplaces = {r.marketplace for r in us_recent}
        de_marketplaces = {r.marketplace for r in de_recent}

        assert us_marketplaces == {"EBAY_US"} or us_marketplaces == set()
        # de_recent should only contain EBAY_DE records if any
        if de_recent:
            assert all(r.marketplace == "EBAY_DE" for r in de_recent)