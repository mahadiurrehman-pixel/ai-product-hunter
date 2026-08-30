"""
Tests for eBay API caching, retry, deduplication, and monitoring.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
import time

import pytest

from services.ebay.cache import (
    EbayCacheService,
    is_fresh,
    normalize_query,
    generate_search_cache_key,
)
from services.ebay.client import EbayClient
from services.ebay.exceptions import (
    EbayRateLimitError,
    EbayNetworkError,
    EbayAPIError,
    EbayAuthenticationError,
)


# =============================================================================
# Freshness Utility Tests
# =============================================================================

class TestIsFresh:
    def test_fresh_data(self):
        now = datetime.now(timezone.utc)
        fetched = now - timedelta(hours=1)
        assert is_fresh(fetched, ttl_seconds=86400, now=now) is True

    def test_stale_data(self):
        now = datetime.now(timezone.utc)
        fetched = now - timedelta(hours=25)
        assert is_fresh(fetched, ttl_seconds=86400, now=now) is False

    def test_boundary_minus_one_second(self):
        now = datetime.now(timezone.utc)
        fetched = now - timedelta(seconds=86399)
        assert is_fresh(fetched, ttl_seconds=86400, now=now) is True

    def test_boundary_exact(self):
        now = datetime.now(timezone.utc)
        fetched = now - timedelta(seconds=86400)
        assert is_fresh(fetched, ttl_seconds=86400, now=now) is False

    def test_boundary_plus_one_second(self):
        now = datetime.now(timezone.utc)
        fetched = now - timedelta(seconds=86401)
        assert is_fresh(fetched, ttl_seconds=86400, now=now) is False

    def test_none_timestamp(self):
        now = datetime.now(timezone.utc)
        assert is_fresh(None, ttl_seconds=86400, now=now) is False

    def test_naive_datetime_treated_as_utc(self):
        now = datetime.now(timezone.utc)
        fetched = datetime.utcnow() - timedelta(hours=1)
        assert is_fresh(fetched, ttl_seconds=86400, now=now) is True


# =============================================================================
# Query Normalization Tests
# =============================================================================

class TestQueryNormalization:
    def test_strip_whitespace(self):
        assert normalize_query("  AirPods Pro  ") == "airpods pro"

    def test_lowercase(self):
        assert normalize_query("AirPods Pro") == "airpods pro"

    def test_collapse_whitespace(self):
        assert normalize_query("airpods   pro") == "airpods pro"

    def test_equivalent_queries(self):
        q1 = normalize_query("AirPods Pro")
        q2 = normalize_query("airpods pro")
        q3 = normalize_query("  AirPods Pro  ")
        assert q1 == q2 == q3

    def test_meaningful_differences_preserved(self):
        q1 = normalize_query("AirPods Pro")
        q2 = normalize_query("AirPods Pro 2")
        assert q1 != q2

    def test_numbers_preserved(self):
        q = normalize_query("iPhone 15 Pro Max 256GB")
        assert "15" in q
        assert "256" in q

    def test_empty_query(self):
        assert normalize_query("") == ""
        assert normalize_query("   ") == ""

    def test_punctuation_stripped(self):
        assert normalize_query("earbuds,") == "earbuds"
        assert normalize_query("earbuds!") == "earbuds"


# =============================================================================
# Cache Key Tests
# =============================================================================

class TestCacheKeyGeneration:
    def test_deterministic(self):
        k1 = generate_search_cache_key("earbuds", "EBAY_US")
        k2 = generate_search_cache_key("earbuds", "EBAY_US")
        assert k1 == k2

    def test_different_queries(self):
        k1 = generate_search_cache_key("earbuds", "EBAY_US")
        k2 = generate_search_cache_key("speaker", "EBAY_US")
        assert k1 != k2

    def test_different_marketplaces(self):
        k1 = generate_search_cache_key("earbuds", "EBAY_US")
        k2 = generate_search_cache_key("earbuds", "EBAY_GB")
        assert k1 != k2

    def test_different_limits(self):
        k1 = generate_search_cache_key("earbuds", "EBAY_US", limit=20)
        k2 = generate_search_cache_key("earbuds", "EBAY_US", limit=50)
        assert k1 != k2

    def test_different_sort(self):
        k1 = generate_search_cache_key("earbuds", "EBAY_US", sort="relevance")
        k2 = generate_search_cache_key("earbuds", "EBAY_US", sort="price")
        assert k1 != k2

    def test_case_insensitive(self):
        k1 = generate_search_cache_key("Wireless Earbuds", "EBAY_US")
        k2 = generate_search_cache_key("wireless earbuds", "EBAY_US")
        assert k1 == k2

    def test_different_categories(self):
        k1 = generate_search_cache_key(
            "earbuds", "EBAY_US", category_id="123"
        )
        k2 = generate_search_cache_key(
            "earbuds", "EBAY_US", category_id="456"
        )
        assert k1 != k2

    def test_different_price_filters(self):
        k1 = generate_search_cache_key(
            "earbuds", "EBAY_US", min_price=10.0
        )
        k2 = generate_search_cache_key(
            "earbuds", "EBAY_US", min_price=20.0
        )
        assert k1 != k2

    def test_key_is_sha256_hex(self):
        key = generate_search_cache_key("test", "EBAY_US")
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_normalized_query_produces_same_key(self):
        k1 = generate_search_cache_key("  AirPods Pro  ", "EBAY_US")
        k2 = generate_search_cache_key("airpods pro", "EBAY_US")
        assert k1 == k2


# =============================================================================
# Cache Service Tests
# =============================================================================

class TestEbayCacheService:
    @pytest.fixture
    def mock_client(self):
        client = Mock(spec=EbayClient)
        client.marketplace_id = "EBAY_US"
        return client

    @pytest.fixture
    def cache_service(self, mock_client):
        svc = EbayCacheService(ebay_client=mock_client)
        svc._max_retries = 1  # Speed up tests
        svc._retry_base_delay = 0.01
        return svc

    def test_cache_miss_calls_api(self, cache_service, mock_client):
        mock_client.search_items.return_value = {
            "total": 5, "items": [], "items_count": 0,
        }
        with patch.object(
            cache_service, "_get_cached_search", return_value=None
        ), patch.object(cache_service, "_cache_search_results"):
            cache_service.search_items("earbuds", limit=5)
        mock_client.search_items.assert_called_once()

    def test_cache_hit_skips_api(self, cache_service, mock_client):
        cached = {
            "total": 5, "items": [{"item_id": "v1|1|0"}],
            "items_count": 1, "cached": True,
        }
        with patch.object(
            cache_service, "_get_cached_search", return_value=cached
        ):
            result = cache_service.search_items("earbuds", limit=5)
        mock_client.search_items.assert_not_called()
        assert result["cached"] is True

    def test_api_failure_returns_stale(
        self, cache_service, mock_client
    ):
        mock_client.search_items.side_effect = Exception("API down")
        stale = {
            "total": 3, "items": [{"item_id": "v1|s|0"}],
            "items_count": 1, "cached": True,
        }
        call_count = [0]

        def mock_get(key, db=None, ignore_freshness=False):
            call_count[0] += 1
            if ignore_freshness:
                return stale
            return None

        with patch.object(
            cache_service, "_get_cached_search", side_effect=mock_get
        ):
            result = cache_service.search_items("earbuds")
        assert result["cached"] is True

    def test_api_failure_no_stale_raises(
        self, cache_service, mock_client
    ):
        mock_client.search_items.side_effect = Exception("API down")
        with patch.object(
            cache_service, "_get_cached_search", return_value=None
        ):
            with pytest.raises(Exception, match="API down"):
                cache_service.search_items("earbuds")

    def test_item_details_cache_hit(self, cache_service, mock_client):
        cached = {"item_id": "v1|1|0", "cached": True}
        with patch.object(
            cache_service, "_get_cached_item", return_value=cached
        ):
            result = cache_service.get_item_details("v1|1|0")
        mock_client.get_item_details.assert_not_called()
        assert result["cached"] is True

    def test_item_details_cache_miss(self, cache_service, mock_client):
        mock_client.get_item_details.return_value = {
            "item_id": "v1|1|0", "title": "Test",
        }
        with patch.object(
            cache_service, "_get_cached_item", return_value=None
        ), patch.object(cache_service, "_cache_item_details"):
            cache_service.get_item_details("v1|1|0")
        mock_client.get_item_details.assert_called_once()

    def test_ttl_properties(self, cache_service):
        assert cache_service.search_ttl_seconds > 0
        assert cache_service.item_ttl_seconds > 0


# =============================================================================
# Retry Tests
# =============================================================================

class TestRetryLogic:
    @pytest.fixture
    def mock_client(self):
        client = Mock(spec=EbayClient)
        client.marketplace_id = "EBAY_US"
        return client

    def test_retry_on_rate_limit(self, mock_client):
        svc = EbayCacheService(ebay_client=mock_client)
        svc._max_retries = 3
        svc._retry_base_delay = 0.01

        mock_client.search_items.side_effect = [
            EbayRateLimitError("rate limited"),
            {"total": 1, "items": [], "items_count": 0},
        ]

        with patch.object(
            svc, "_get_cached_search", return_value=None
        ), patch.object(svc, "_cache_search_results"):
            result = svc.search_items("earbuds")

        assert mock_client.search_items.call_count == 2

    def test_retry_on_network_error(self, mock_client):
        svc = EbayCacheService(ebay_client=mock_client)
        svc._max_retries = 2
        svc._retry_base_delay = 0.01

        mock_client.search_items.side_effect = [
            EbayNetworkError("timeout"),
            {"total": 1, "items": [], "items_count": 0},
        ]

        with patch.object(
            svc, "_get_cached_search", return_value=None
        ), patch.object(svc, "_cache_search_results"):
            result = svc.search_items("earbuds")

        assert mock_client.search_items.call_count == 2

    def test_no_retry_on_auth_error(self, mock_client):
        svc = EbayCacheService(ebay_client=mock_client)
        svc._max_retries = 3
        svc._retry_base_delay = 0.01

        mock_client.search_items.side_effect = (
            EbayAuthenticationError("bad creds")
        )

        with patch.object(
            svc, "_get_cached_search", return_value=None
        ):
            with pytest.raises(EbayAuthenticationError):
                svc.search_items("earbuds")

        assert mock_client.search_items.call_count == 1

    def test_no_retry_on_404(self, mock_client):
        svc = EbayCacheService(ebay_client=mock_client)
        svc._max_retries = 3
        svc._retry_base_delay = 0.01

        mock_client.search_items.side_effect = EbayAPIError(
            "not found", status_code=404
        )

        with patch.object(
            svc, "_get_cached_search", return_value=None
        ):
            with pytest.raises(EbayAPIError):
                svc.search_items("earbuds")

        assert mock_client.search_items.call_count == 1

    def test_retry_exhausted_raises(self, mock_client):
        svc = EbayCacheService(ebay_client=mock_client)
        svc._max_retries = 2
        svc._retry_base_delay = 0.01

        mock_client.search_items.side_effect = EbayNetworkError("fail")

        with patch.object(
            svc, "_get_cached_search", return_value=None
        ):
            with pytest.raises(EbayNetworkError):
                svc.search_items("earbuds")

        assert mock_client.search_items.call_count == 2

    def test_backoff_calculation(self, mock_client):
        svc = EbayCacheService(ebay_client=mock_client)
        svc._retry_base_delay = 1.0
        svc._retry_max_delay = 30.0

        assert svc._calculate_backoff(1) == 1.0
        assert svc._calculate_backoff(2) == 2.0
        assert svc._calculate_backoff(3) == 4.0
        assert svc._calculate_backoff(10) == 30.0  # Capped