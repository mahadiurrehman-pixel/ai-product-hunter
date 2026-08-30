"""
Regression test for _log_request() session leak fix.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestLogRequestSessionCleanup:

    def test_log_request_uses_context_manager(self):
        """_log_request must use get_db_context, not next(get_db())."""
        from services.ebay.client import EbayClient
        import inspect

        source = inspect.getsource(EbayClient._log_request)
        assert "next(get_db())" not in source
        assert "get_db_context" in source

    @patch("database.connection.get_db_context")
    def test_log_request_closes_session_on_success(self, mock_ctx):
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

        mock_ctx.return_value.__exit__.assert_called_once()

    @patch("database.connection.get_db_context")
    def test_log_request_closes_session_on_commit_failure(self, mock_ctx):
        mock_db = MagicMock()
        mock_db.commit.side_effect = Exception("DB locked")
        mock_ctx.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.return_value.__exit__ = MagicMock(return_value=False)

        from services.ebay.client import EbayClient
        client = EbayClient.__new__(EbayClient)

        client._log_request(
            endpoint="/test",
            method="GET",
            status_code=500,
            response_time_ms=1000,
            error_occurred=True,
        )

        mock_ctx.return_value.__exit__.assert_called_once()

    @patch("database.connection.get_db_context")
    def test_log_request_does_not_raise_on_total_failure(self, mock_ctx):
        mock_ctx.side_effect = Exception("Cannot connect to DB")

        from services.ebay.client import EbayClient
        client = EbayClient.__new__(EbayClient)

        client._log_request(
            endpoint="/test",
            method="GET",
            status_code=200,
            response_time_ms=50,
        )