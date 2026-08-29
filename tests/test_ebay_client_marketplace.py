"""
Tests for EbayClient marketplace selection.
"""
import json
from unittest.mock import Mock, patch

import pytest

from services.ebay.client import EbayClient
from services.ebay.marketplace import EbayMarketplace


class TestEbayClientMarketplaceSelection:
    """Test that EbayClient correctly uses selected marketplace."""

    @pytest.fixture
    def mock_auth(self):
        auth = Mock()
        auth.get_application_token.return_value = "mock_token_xyz"
        return auth

    @pytest.fixture
    def mock_rate_limiter(self):
        limiter = Mock()
        limiter.acquire.return_value = True
        return limiter

    @pytest.fixture
    def mock_search_response(self):
        with open('tests/mocks/ebay_search_response.json') as f:
            return json.load(f)

    def test_default_marketplace_from_settings(self, mock_auth, mock_rate_limiter):
        """Without marketplace arg, uses settings default (EBAY_US)."""
        client = EbayClient(auth=mock_auth, rate_limiter=mock_rate_limiter)
        # Default in settings is EBAY_US
        assert client.marketplace == EbayMarketplace.US
        assert client.marketplace_id == "EBAY_US"

    def test_explicit_us_marketplace(self, mock_auth, mock_rate_limiter):
        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_rate_limiter,
            marketplace=EbayMarketplace.US,
        )
        assert client.marketplace == EbayMarketplace.US
        assert client.marketplace_id == "EBAY_US"

    def test_explicit_uk_marketplace(self, mock_auth, mock_rate_limiter):
        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_rate_limiter,
            marketplace=EbayMarketplace.UK,
        )
        assert client.marketplace == EbayMarketplace.UK
        assert client.marketplace_id == "EBAY_GB"

    def test_explicit_germany_marketplace(self, mock_auth, mock_rate_limiter):
        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_rate_limiter,
            marketplace=EbayMarketplace.GERMANY,
        )
        assert client.marketplace == EbayMarketplace.GERMANY
        assert client.marketplace_id == "EBAY_DE"

    def test_explicit_australia_marketplace(self, mock_auth, mock_rate_limiter):
        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_rate_limiter,
            marketplace=EbayMarketplace.AUSTRALIA,
        )
        assert client.marketplace == EbayMarketplace.AUSTRALIA
        assert client.marketplace_id == "EBAY_AU"

    def test_explicit_canada_marketplace(self, mock_auth, mock_rate_limiter):
        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_rate_limiter,
            marketplace=EbayMarketplace.CANADA,
        )
        assert client.marketplace == EbayMarketplace.CANADA
        assert client.marketplace_id == "EBAY_CA"

    def test_all_five_marketplaces_supported(
        self, mock_auth, mock_rate_limiter
    ):
        """Can instantiate EbayClient with any of the 5 marketplaces."""
        marketplaces = [
            EbayMarketplace.US,
            EbayMarketplace.UK,
            EbayMarketplace.GERMANY,
            EbayMarketplace.AUSTRALIA,
            EbayMarketplace.CANADA,
        ]
        for mp in marketplaces:
            client = EbayClient(
                auth=mock_auth,
                rate_limiter=mock_rate_limiter,
                marketplace=mp,
            )
            assert client.marketplace == mp


class TestEbayClientMarketplaceHeader:
    """Test that marketplace ID is used in API request headers."""

    @pytest.fixture
    def mock_search_response(self):
        with open('tests/mocks/ebay_search_response.json') as f:
            return json.load(f)

    def _setup_mocks(self, mock_client_class, mock_response_data):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.return_value = mock_response

        mock_client_class.return_value = mock_client
        return mock_client

    @patch('httpx.Client')
    def test_us_marketplace_sent_in_header(
        self, mock_client_class, mock_search_response
    ):
        mock_client = self._setup_mocks(
            mock_client_class, mock_search_response
        )

        mock_auth = Mock()
        mock_auth.get_application_token.return_value = "token"
        mock_limiter = Mock()
        mock_limiter.acquire.return_value = True

        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_limiter,
            marketplace=EbayMarketplace.US,
        )
        client.search_items("test", limit=5)

        call_kwargs = mock_client.request.call_args[1]
        headers = call_kwargs["headers"]
        assert headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_US"

    @patch('httpx.Client')
    def test_uk_marketplace_sent_in_header(
        self, mock_client_class, mock_search_response
    ):
        mock_client = self._setup_mocks(
            mock_client_class, mock_search_response
        )

        mock_auth = Mock()
        mock_auth.get_application_token.return_value = "token"
        mock_limiter = Mock()
        mock_limiter.acquire.return_value = True

        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_limiter,
            marketplace=EbayMarketplace.UK,
        )
        client.search_items("test", limit=5)

        call_kwargs = mock_client.request.call_args[1]
        headers = call_kwargs["headers"]
        assert headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_GB"

    @patch('httpx.Client')
    def test_germany_marketplace_sent_in_header(
        self, mock_client_class, mock_search_response
    ):
        mock_client = self._setup_mocks(
            mock_client_class, mock_search_response
        )

        mock_auth = Mock()
        mock_auth.get_application_token.return_value = "token"
        mock_limiter = Mock()
        mock_limiter.acquire.return_value = True

        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_limiter,
            marketplace=EbayMarketplace.GERMANY,
        )
        client.search_items("test", limit=5)

        call_kwargs = mock_client.request.call_args[1]
        headers = call_kwargs["headers"]
        assert headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_DE"

    @patch('httpx.Client')
    def test_australia_marketplace_sent_in_header(
        self, mock_client_class, mock_search_response
    ):
        mock_client = self._setup_mocks(
            mock_client_class, mock_search_response
        )

        mock_auth = Mock()
        mock_auth.get_application_token.return_value = "token"
        mock_limiter = Mock()
        mock_limiter.acquire.return_value = True

        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_limiter,
            marketplace=EbayMarketplace.AUSTRALIA,
        )
        client.search_items("test", limit=5)

        call_kwargs = mock_client.request.call_args[1]
        headers = call_kwargs["headers"]
        assert headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_AU"

    @patch('httpx.Client')
    def test_canada_marketplace_sent_in_header(
        self, mock_client_class, mock_search_response
    ):
        mock_client = self._setup_mocks(
            mock_client_class, mock_search_response
        )

        mock_auth = Mock()
        mock_auth.get_application_token.return_value = "token"
        mock_limiter = Mock()
        mock_limiter.acquire.return_value = True

        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_limiter,
            marketplace=EbayMarketplace.CANADA,
        )
        client.search_items("test", limit=5)

        call_kwargs = mock_client.request.call_args[1]
        headers = call_kwargs["headers"]
        assert headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_CA"


class TestEbayClientMarketplaceInResults:
    """Test that marketplace is injected into parsed results."""

    @pytest.fixture
    def mock_search_response(self):
        with open('tests/mocks/ebay_search_response.json') as f:
            return json.load(f)

    @patch('httpx.Client')
    def test_marketplace_injected_into_response(
        self, mock_client_class, mock_search_response
    ):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        mock_auth = Mock()
        mock_auth.get_application_token.return_value = "token"
        mock_limiter = Mock()
        mock_limiter.acquire.return_value = True

        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_limiter,
            marketplace=EbayMarketplace.GERMANY,
        )
        result = client.search_items("test", limit=5)

        # Top-level marketplace
        assert result["marketplace"] == "EBAY_DE"

        # Every parsed item has marketplace field
        for item in result["items"]:
            assert item["marketplace"] == "EBAY_DE"

    @patch('httpx.Client')
    def test_uk_marketplace_in_results(
        self, mock_client_class, mock_search_response
    ):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client

        mock_auth = Mock()
        mock_auth.get_application_token.return_value = "token"
        mock_limiter = Mock()
        mock_limiter.acquire.return_value = True

        client = EbayClient(
            auth=mock_auth,
            rate_limiter=mock_limiter,
            marketplace=EbayMarketplace.UK,
        )
        result = client.search_items("test", limit=5)

        assert result["marketplace"] == "EBAY_GB"
        for item in result["items"]:
            assert item["marketplace"] == "EBAY_GB"