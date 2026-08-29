"""
Tests for eBay OAuth authentication.
"""
import base64
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
import httpx

from services.ebay.auth import EbayAuth
from services.ebay.exceptions import (
    EbayAuthenticationError,
    EbayNetworkError,
)


class TestEbayAuth:
    """Test eBay OAuth authentication."""

    def test_init_with_credentials(self):
        """Test initialization with credentials."""
        auth = EbayAuth(
            app_id="test_app_id", cert_id="test_cert_id", environment="sandbox"
        )

        assert auth.app_id == "test_app_id"
        assert auth.cert_id == "test_cert_id"
        assert auth.environment == "sandbox"

    def test_init_without_credentials_logs_warning(self, caplog):
        """Test initialization without credentials logs warning."""
        auth = EbayAuth(app_id="", cert_id="")

        assert "eBay credentials not configured" in caplog.text

    def test_get_auth_header(self):
        """Test Basic auth header generation."""
        auth = EbayAuth(app_id="my_app_id", cert_id="my_cert_id")

        header = auth._get_auth_header()

        # Verify format
        assert header.startswith("Basic ")

        # Decode and verify
        encoded = header.replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode()

        assert decoded == "my_app_id:my_cert_id"

    def test_get_auth_header_missing_credentials(self):
        """Test auth header with missing credentials."""
        auth = EbayAuth(app_id="", cert_id="")

        with pytest.raises(EbayAuthenticationError) as exc_info:
            auth._get_auth_header()

        assert "not configured" in str(exc_info.value)

    @patch("httpx.Client")
    def test_get_application_token_success(self, mock_client_class):
        """Test successful token retrieval."""
        # Load mock response
        with open("tests/mocks/ebay_oauth.json") as f:
            mock_response_data = json.load(f)

        # Setup mock
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.return_value = mock_response

        mock_client_class.return_value = mock_client

        # Test
        auth = EbayAuth(app_id="test_app", cert_id="test_cert")

        token = auth.get_application_token()

        assert token == mock_response_data["access_token"]
        assert auth._access_token == token
        assert auth._token_expires_at is not None

    @patch("httpx.Client")
    def test_get_application_token_uses_cache(self, mock_client_class):
        """Test that cached token is used."""
        auth = EbayAuth(app_id="test_app", cert_id="test_cert")

        # Set cached token
        auth._access_token = "cached_token"
        auth._token_expires_at = datetime.utcnow() + timedelta(hours=1)

        token = auth.get_application_token()

        # Should not call API
        mock_client_class.assert_not_called()
        assert token == "cached_token"

    @patch("httpx.Client")
    def test_get_application_token_401_error(self, mock_client_class):
        """Test handling of 401 authentication error."""
        mock_response = Mock()
        mock_response.status_code = 401

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.return_value = mock_response

        mock_client_class.return_value = mock_client

        auth = EbayAuth(app_id="invalid_app", cert_id="invalid_cert")

        with pytest.raises(EbayAuthenticationError) as exc_info:
            auth.get_application_token()

        assert "Invalid eBay credentials" in str(exc_info.value)

    @patch("httpx.Client")
    def test_get_application_token_missing_access_token(self, mock_client_class):
        """Test handling of response missing access_token."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "token_type": "Bearer"
        }  # Missing access_token

        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.return_value = mock_response

        mock_client_class.return_value = mock_client

        auth = EbayAuth(app_id="test_app", cert_id="test_cert")

        with pytest.raises(EbayAuthenticationError) as exc_info:
            auth.get_application_token()

        assert "missing access_token" in str(exc_info.value)

    @patch("httpx.Client")
    def test_get_application_token_timeout(self, mock_client_class):
        """Test handling of timeout error."""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.side_effect = httpx.TimeoutException("Timeout")

        mock_client_class.return_value = mock_client

        auth = EbayAuth(app_id="test_app", cert_id="test_cert")

        with pytest.raises(EbayNetworkError) as exc_info:
            auth.get_application_token()

        assert "timeout" in str(exc_info.value).lower()

    @patch("httpx.Client")
    def test_get_application_token_network_error(self, mock_client_class):
        """Test handling of network error."""
        mock_client = Mock()
        mock_client.__enter__ = Mock(return_value=mock_client)
        mock_client.__exit__ = Mock(return_value=False)
        mock_client.post.side_effect = httpx.RequestError("Connection failed")

        mock_client_class.return_value = mock_client

        auth = EbayAuth(app_id="test_app", cert_id="test_cert")

        with pytest.raises(EbayNetworkError):
            auth.get_application_token()

    def test_clear_token(self):
        """Test clearing cached token."""
        auth = EbayAuth(app_id="test_app", cert_id="test_cert")

        auth._access_token = "token"
        auth._token_expires_at = datetime.utcnow() + timedelta(hours=1)

        auth.clear_token()

        assert auth._access_token is None
        assert auth._token_expires_at is None

    def test_credentials_not_logged(self, caplog):
        """Test that credentials are never logged."""
        auth = EbayAuth(app_id="secret_app_id", cert_id="secret_cert_id")

        # Generate auth header
        try:
            auth._get_auth_header()
        except:
            pass

        # Check logs don't contain credentials
        assert "secret_app_id" not in caplog.text
        assert "secret_cert_id" not in caplog.text
