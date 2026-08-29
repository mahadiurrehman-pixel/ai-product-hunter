"""
Tests for eBay Browse API client.
"""
import json
from unittest.mock import Mock, patch, MagicMock

import pytest
import httpx

from services.ebay.client import EbayClient
from services.ebay.auth import EbayAuth
from services.ebay.rate_limiter import RateLimiter
from services.ebay.exceptions import (
    EbayAPIError,
    EbayAuthenticationError,
    EbayRateLimitError,
    EbayInvalidResponseError,
    EbayNetworkError,
)
from utils.exceptions import ValidationError


class TestEbayClient:
    """Test eBay Browse API client."""

    @pytest.fixture
    def mock_auth(self):
        """Mock authentication."""
        auth = Mock(spec=EbayAuth)
        auth.get_application_token.return_value = "mock_token_123"
        return auth

    @pytest.fixture
    def mock_rate_limiter(self):
        """Mock rate limiter."""
        limiter = Mock(spec=RateLimiter)
        limiter.acquire.return_value = True
        return limiter

    @pytest.fixture
    def client(self, mock_auth, mock_rate_limiter):
        """Create client with mocked dependencies."""
        return EbayClient(auth=mock_auth, rate_limiter=mock_rate_limiter)

    @pytest.fixture
    def mock_search_response(self):
        """Load mock search response."""
        with open("tests/mocks/ebay_search_response.json") as f:
            return json.load(f)

    def test_init(self):
        """Test client initialization."""
        client = EbayClient()

        assert client.auth is not None
        assert client.rate_limiter is not None
        assert client.parser is not None

    def test_search_items_validation(self, client):
        """Test search input validation."""
        # Empty query
        with pytest.raises(ValidationError):
            client.search_items(query="")

        # Query too short
        with pytest.raises(ValidationError):
            client.search_items(query="a")

        # Invalid limit
        with pytest.raises(ValidationError):
            client.search_items(query="test", limit=0)

        with pytest.raises(ValidationError):
            client.search_items(query="test", limit=300)

        # Invalid offset
        with pytest.raises(ValidationError):
            client.search_items(query="test", offset=-1)

    @patch("httpx.Client")
    def test_search_items_success(
        self, mock_client_class, client, mock_search_response
    ):
        """Test successful search."""
        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.return_value = mock_response

        mock_client_class.return_value = mock_client

        # Test
        result = client.search_items(query="wireless earbuds", limit=5)

        assert result["total"] == 1523
        assert result["items_count"] == 5
        assert len(result["items"]) == 5

        # Verify first item
        first_item = result["items"][0]
        assert first_item["item_id"] == "v1|334567891234|0"
        assert (
            first_item["title"]
            == "Wireless Bluetooth Earbuds with Charging Case - Noise Cancelling"
        )
        assert float(first_item["price_value"]) == 29.99

    @patch("httpx.Client")
    def test_search_items_with_filters(
        self, mock_client_class, client, mock_search_response
    ):
        """Test search with filters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_search_response

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.return_value = mock_response

        mock_client_class.return_value = mock_client

        result = client.search_items(
            query="earbuds",
            category_id="15032",
            min_price=10.0,
            max_price=50.0,
            condition="NEW",
        )

        # Verify request was made with filters
        call_kwargs = mock_client.request.call_args[1]
        params = call_kwargs["params"]

        assert "filter" in params
        assert "price:[10.0..50.0]" in params["filter"]
        assert "conditions:{NEW}" in params["filter"]

    @patch("httpx.Client")
    def test_search_items_401_error(self, mock_client_class, client):
        """Test handling of 401 authentication error."""
        mock_response = Mock()
        mock_response.status_code = 401

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.return_value = mock_response

        mock_client_class.return_value = mock_client

        with pytest.raises(EbayAuthenticationError):
            client.search_items(query="test")

    @patch("httpx.Client")
    def test_search_items_429_rate_limit(self, mock_client_class, client):
        """Test handling of 429 rate limit error."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.headers = {"Retry-After": "60"}

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.return_value = mock_response

        mock_client_class.return_value = mock_client

        with pytest.raises(EbayRateLimitError) as exc_info:
            client.search_items(query="test")

        assert exc_info.value.retry_after == 60

    @patch("httpx.Client")
    def test_search_items_404_error(self, mock_client_class, client):
        """Test handling of 404 error."""
        mock_response = Mock()
        mock_response.status_code = 404

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.return_value = mock_response

        mock_client_class.return_value = mock_client

        with pytest.raises(EbayAPIError) as exc_info:
            client.search_items(query="test")

        assert "not found" in str(exc_info.value).lower()

    @patch("httpx.Client")
    def test_search_items_500_error(self, mock_client_class, client):
        """Test handling of 500 server error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.return_value = mock_response

        mock_client_class.return_value = mock_client

        with pytest.raises(EbayAPIError) as exc_info:
            client.search_items(query="test")

        assert "server error" in str(exc_info.value).lower()

    @patch("httpx.Client")
    def test_search_items_timeout(self, mock_client_class, client):
        """Test handling of timeout."""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.side_effect = httpx.TimeoutException("Timeout")

        mock_client_class.return_value = mock_client

        with pytest.raises(EbayNetworkError):
            client.search_items(query="test")

    @patch("httpx.Client")
    def test_search_items_network_error(self, mock_client_class, client):
        """Test handling of network error."""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.side_effect = httpx.RequestError("Network error")

        mock_client_class.return_value = mock_client

        with pytest.raises(EbayNetworkError):
            client.search_items(query="test")

    @patch("httpx.Client")
    def test_search_items_invalid_json(self, mock_client_class, client):
        """Test handling of invalid JSON response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid", "", 0)

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.request.return_value = mock_response

        mock_client_class.return_value = mock_client

        with pytest.raises(EbayInvalidResponseError):
            client.search_items(query="test")

    def test_rate_limiter_called(self, client, mock_rate_limiter):
        """Test that rate limiter is called before request."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"itemSummaries": []}

            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.request.return_value = mock_response

            mock_client_class.return_value = mock_client

            client.search_items(query="test")

            # Verify rate limiter was called
            mock_rate_limiter.acquire.assert_called_once()

    def test_auth_called(self, client, mock_auth):
        """Test that authentication is called before request."""
        with patch("httpx.Client") as mock_client_class:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"itemSummaries": []}

            mock_client = Mock()
            mock_client.__enter__ = Mock(return_value=mock_client)
            mock_client.__exit__ = Mock(return_value=False)
            mock_client.request.return_value = mock_response

            mock_client_class.return_value = mock_client

            client.search_items(query="test")

            # Verify auth was called
            mock_auth.get_application_token.assert_called_once()
