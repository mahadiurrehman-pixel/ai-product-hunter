"""
Integration tests for eBay service with database.
"""
import json
from unittest.mock import Mock, patch
from datetime import timedelta

import pytest

from services.ebay.client import EbayClient
from services.ebay.repository import EbayListingRepository
from models.ebay import EbayListing


class TestEbayIntegration:
    """Test eBay service integration with database."""

    @pytest.fixture
    def mock_search_response(self):
        """Load mock search response."""
        with open("tests/mocks/ebay_search_response.json") as f:
            return json.load(f)

    @patch("services.ebay.client.EbayAuth")  # Mock at client import level
    @patch("httpx.Client")
    def test_search_and_save_to_database(
        self, mock_client_class, mock_auth_class, db_session, mock_search_response
    ):
        """Test complete flow: search → parse → save to database."""
        # Setup mock authentication
        mock_auth_instance = Mock()
        mock_auth_instance.get_application_token.return_value = "mock_token_12345"
        mock_auth_class.return_value = mock_auth_instance

        # Setup mock HTTP client for Browse API request
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.return_value = mock_response

        mock_client_class.return_value = mock_client

        # Perform search
        client = EbayClient()
        result = client.search_items(query="wireless earbuds", limit=5)

        # Save to database
        saved_listings = EbayListingRepository.save_listings_bulk(
            db_session, result["items"]
        )

        # Verify saved
        assert len(saved_listings) == 5

        # Verify can retrieve
        first_listing = EbayListingRepository.get_by_item_id(
            db_session, "v1|334567891234|0"
        )

        assert first_listing is not None
        assert (
            first_listing.title
            == "Wireless Bluetooth Earbuds with Charging Case - Noise Cancelling"
        )
        assert float(first_listing.price_value) == 29.99
        assert first_listing.estimated_sold_quantity == 143

    def test_save_duplicate_listing_updates(self, db_session):
        """Test that saving duplicate item_id updates existing record."""
        from datetime import datetime

        # Create initial listing
        listing_data = {
            "item_id": "v1|123|0",
            "title": "Original Title",
            "price_value": 10.0,
            "price_currency": "USD",
            "item_web_url": "https://ebay.com/itm/123",
            "raw_data": {},
            "fetched_at": datetime.utcnow(),
        }

        first_save = EbayListingRepository.save_listing(db_session, listing_data)
        first_id = first_save.id

        # Update with same item_id
        listing_data["title"] = "Updated Title"
        listing_data["price_value"] = 15.0
        listing_data["fetched_at"] = datetime.utcnow()

        second_save = EbayListingRepository.save_listing(db_session, listing_data)

        # Should be same record (same ID)
        assert second_save.id == first_id
        assert second_save.title == "Updated Title"
        assert float(second_save.price_value) == 15.0

        # Verify only one record exists
        all_listings = (
            db_session.query(EbayListing)
            .filter(EbayListing.item_id == "v1|123|0")
            .all()
        )

        assert len(all_listings) == 1
