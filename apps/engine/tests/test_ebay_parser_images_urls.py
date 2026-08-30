"""
Tests for EbayParser image and listing URL extraction and persistence.
"""
from decimal import Decimal
from datetime import datetime
import pytest

from services.ebay.parser import EbayParser
from services.ebay.repository import EbayListingRepository
from models.ebay import EbayListing


class TestEbayParserImageAndUrlExtraction:
    """Test image_url and item_web_url parsing edge cases."""

    def test_extract_standard_image_and_url(self):
        item_data = {
            "itemId": "v1|test1|0",
            "title": "Sample Item",
            "price": {"value": "49.99", "currency": "USD"},
            "image": {"imageUrl": "https://i.ebayimg.com/images/g/test/s-l1600.jpg"},
            "itemWebUrl": "https://www.ebay.com/itm/test1",
        }
        parsed = EbayParser.parse_item_summary(item_data, marketplace="EBAY_US")
        assert parsed["image_url"] == "https://i.ebayimg.com/images/g/test/s-l1600.jpg"
        assert parsed["item_web_url"] == "https://www.ebay.com/itm/test1"
        assert parsed["marketplace"] == "EBAY_US"

    def test_extract_missing_image_returns_none(self):
        item_data = {
            "itemId": "v1|test2|0",
            "title": "Item Without Image",
            "price": {"value": "10.00", "currency": "USD"},
            "image": None,
            "itemWebUrl": "https://www.ebay.com/itm/test2",
        }
        parsed = EbayParser.parse_item_summary(item_data)
        assert parsed["image_url"] is None
        assert parsed["item_web_url"] == "https://www.ebay.com/itm/test2"

    def test_extract_malformed_image_structure(self):
        item_data = {
            "itemId": "v1|test3|0",
            "title": "Item With Malformed Image",
            "price": {"value": "15.00", "currency": "USD"},
            "image": 12345,  # Invalid type
            "additionalImages": "not-a-list",
            "itemWebUrl": "https://www.ebay.com/itm/test3",
        }
        parsed = EbayParser.parse_item_summary(item_data)
        assert parsed["image_url"] is None
        assert parsed["additional_images"] is None

    def test_extract_missing_url_returns_none(self):
        item_data = {
            "itemId": "v1|test4|0",
            "title": "Item Without URL",
            "price": {"value": "20.00", "currency": "USD"},
            "image": {"imageUrl": "https://img.com/pic.jpg"},
            "itemWebUrl": None,
        }
        parsed = EbayParser.parse_item_summary(item_data)
        assert parsed["image_url"] == "https://img.com/pic.jpg"
        assert parsed["item_web_url"] is None

    def test_extract_alternate_url_keys(self):
        item_data = {
            "itemId": "v1|test5|0",
            "title": "Item With Alt URL",
            "price": {"value": "25.00", "currency": "GBP"},
            "item_web_url": "https://www.ebay.co.uk/itm/test5",
        }
        parsed = EbayParser.parse_item_summary(item_data, marketplace="EBAY_GB")
        assert parsed["item_web_url"] == "https://www.ebay.co.uk/itm/test5"


class TestEbayListingPersistenceWithImageAndUrl:
    """Test image and URL persistence in database."""

    def test_save_listing_with_image_and_url(self, db_session):
        data = {
            "item_id": "v1|persist_1|0",
            "marketplace": "EBAY_US",
            "title": "Persist Test",
            "price_value": Decimal("19.99"),
            "price_currency": "USD",
            "image_url": "https://example.com/image.jpg",
            "item_web_url": "https://www.ebay.com/itm/persist_1",
            "raw_data": {},
            "fetched_at": datetime.utcnow(),
        }
        listing = EbayListingRepository.save_listing(db_session, data)
        assert listing.image_url == "https://example.com/image.jpg"
        assert listing.item_web_url == "https://www.ebay.com/itm/persist_1"
        assert listing.item_url == "https://www.ebay.com/itm/persist_1"

    def test_save_listing_with_null_image_and_url(self, db_session):
        data = {
            "item_id": "v1|persist_null|0",
            "marketplace": "EBAY_US",
            "title": "Persist Nulls",
            "price_value": Decimal("19.99"),
            "price_currency": "USD",
            "image_url": None,
            "item_web_url": None,
            "raw_data": {},
            "fetched_at": datetime.utcnow(),
        }
        listing = EbayListingRepository.save_listing(db_session, data)
        assert listing.image_url is None
        assert listing.item_web_url is None

    def test_upsert_updates_image_and_url(self, db_session):
        data = {
            "item_id": "v1|upsert_img|0",
            "marketplace": "EBAY_US",
            "title": "Initial",
            "price_value": Decimal("10.00"),
            "price_currency": "USD",
            "image_url": None,
            "item_web_url": None,
            "raw_data": {},
            "fetched_at": datetime.utcnow(),
        }
        first = EbayListingRepository.save_listing(db_session, data)
        assert first.image_url is None

        # Update with new image and URL
        data["image_url"] = "https://example.com/new_image.jpg"
        data["item_web_url"] = "https://www.ebay.com/itm/upsert_img"
        second = EbayListingRepository.save_listing(db_session, data)

        assert second.id == first.id
        assert second.image_url == "https://example.com/new_image.jpg"
        assert second.item_web_url == "https://www.ebay.com/itm/upsert_img"