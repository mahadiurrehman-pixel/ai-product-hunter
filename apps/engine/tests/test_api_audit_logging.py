"""
Regression tests for API audit logging integrity.

Ensures APIRequestLog.method is never NULL and all fields
are correctly populated across all request scenarios.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestAPIAuditLogging:
    """Verify _log_request produces valid audit records."""

    def test_log_request_stores_method_separately(self):
        """method must be stored as a separate field, not embedded in endpoint."""
        from services.ebay.client import EbayClient
        import inspect

        source = inspect.getsource(EbayClient._log_request)
        assert "method=" in source, (
            "_log_request must pass method as a field to APIRequestLog"
        )

    @patch("database.connection.get_db_context")
    def test_get_request_logged_correctly(self, mock_ctx):
        """GET requests must log method='GET' and endpoint path only."""
        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from services.ebay.client import EbayClient
        client = EbayClient.__new__(EbayClient)

        client._log_request(
            endpoint="/buy/browse/v1/item_summary/search",
            method="GET",
            status_code=200,
            response_time_ms=150,
        )

        mock_db.add.assert_called_once()
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.method == "GET"
        assert "/buy/browse" in log_entry.endpoint
        assert log_entry.status_code == 200

    @patch("database.connection.get_db_context")
    def test_post_request_logged_correctly(self, mock_ctx):
        """POST requests must log method='POST'."""
        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from services.ebay.client import EbayClient
        client = EbayClient.__new__(EbayClient)

        client._log_request(
            endpoint="/identity/v1/oauth2/token",
            method="POST",
            status_code=200,
            response_time_ms=300,
        )

        mock_db.add.assert_called_once()
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.method == "POST"

    @patch("database.connection.get_db_context")
    def test_failed_request_logged_with_error(self, mock_ctx):
        """Failed requests must log error details."""
        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from services.ebay.client import EbayClient
        client = EbayClient.__new__(EbayClient)

        client._log_request(
            endpoint="/buy/browse/v1/item_summary/search",
            method="GET",
            status_code=401,
            response_time_ms=50,
            error_occurred=True,
            error_message="Authentication failed",
        )

        mock_db.add.assert_called_once()
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.error_occurred is True
        assert log_entry.error_message == "Authentication failed"
        assert log_entry.status_code == 401

    @patch("database.connection.get_db_context")
    def test_timeout_request_logged(self, mock_ctx):
        """Timeout requests must log with error details."""
        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from services.ebay.client import EbayClient
        client = EbayClient.__new__(EbayClient)

        client._log_request(
            endpoint="/buy/browse/v1/item_summary/search",
            method="GET",
            error_occurred=True,
            error_message="Request timeout",
        )

        mock_db.add.assert_called_once()
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.error_occurred is True

    @patch("database.connection.get_db_context")
    def test_429_rate_limit_logged(self, mock_ctx):
        """Rate limit responses must be logged."""
        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from services.ebay.client import EbayClient
        client = EbayClient.__new__(EbayClient)

        client._log_request(
            endpoint="/buy/browse/v1/item_summary/search",
            method="GET",
            status_code=429,
            response_time_ms=10,
            error_occurred=True,
            error_message="Rate limit exceeded",
        )

        mock_db.add.assert_called_once()
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.status_code == 429
        assert log_entry.error_occurred is True

    @patch("database.connection.get_db_context")
    def test_embedded_method_stripped_from_endpoint(self, mock_ctx):
        """If method is embedded in endpoint string, it must be separated."""
        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from services.ebay.client import EbayClient
        client = EbayClient.__new__(EbayClient)

        client._log_request(
            endpoint="GET /buy/browse/v1/item_summary/search",
            method="GET",
            status_code=200,
            response_time_ms=100,
        )

        mock_db.add.assert_called_once()
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.method == "GET"
        assert "GET" not in log_entry.endpoint

    @patch("database.connection.get_db_context")
    def test_logging_failure_does_not_raise(self, mock_ctx):
        """Logging failure must never break the primary request."""
        mock_ctx.side_effect = Exception("Database unavailable")

        from services.ebay.client import EbayClient
        client = EbayClient.__new__(EbayClient)

        # Must NOT raise
        client._log_request(
            endpoint="/test",
            method="GET",
            status_code=200,
        )

    @patch("database.connection.get_db_context")
    def test_method_never_null(self, mock_ctx):
        """method field must always have a value."""
        mock_db = MagicMock()
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from services.ebay.client import EbayClient
        client = EbayClient.__new__(EbayClient)

        client._log_request(
            endpoint="/test",
            method="",
            status_code=200,
        )

        mock_db.add.assert_called_once()
        log_entry = mock_db.add.call_args[0][0]
        assert log_entry.method is not None
        assert log_entry.method == "GET"