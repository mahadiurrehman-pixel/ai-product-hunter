"""
Tests for eBay rate limiter.
"""
import time
from threading import Thread

import pytest

from services.ebay.rate_limiter import RateLimiter
from services.ebay.exceptions import EbayRateLimitError


class TestRateLimiter:
    """Test rate limiter."""

    def test_init(self):
        """Test initialization."""
        limiter = RateLimiter(requests_per_second=5, requests_per_day=1000)

        assert limiter.requests_per_second == 5
        assert limiter.requests_per_day == 1000

    def test_acquire_success(self):
        """Test successful acquisition."""
        limiter = RateLimiter(requests_per_second=10, requests_per_day=1000)

        result = limiter.acquire(block=False)

        assert result is True

    def test_acquire_per_second_limit(self):
        """Test per-second limit enforcement."""
        limiter = RateLimiter(requests_per_second=2, requests_per_day=1000)

        # Should succeed twice
        limiter.acquire(block=False)
        limiter.acquire(block=False)

        # Third should fail
        with pytest.raises(EbayRateLimitError):
            limiter.acquire(block=False)

    def test_acquire_per_day_limit(self):
        """Test per-day limit enforcement."""
        limiter = RateLimiter(requests_per_second=1000, requests_per_day=3)

        # Should succeed 3 times
        limiter.acquire(block=False)
        limiter.acquire(block=False)
        limiter.acquire(block=False)

        # Fourth should fail
        with pytest.raises(EbayRateLimitError):
            limiter.acquire(block=False)

    def test_acquire_blocking(self):
        """Test blocking mode waits for capacity."""
        limiter = RateLimiter(requests_per_second=5, requests_per_day=1000)

        # Fill capacity
        for _ in range(5):
            limiter.acquire(block=False)

        # This should block briefly then succeed
        start = time.time()
        result = limiter.acquire(block=True, timeout=2)
        duration = time.time() - start

        assert result is True
        assert duration > 0.5  # Should have waited
        assert duration < 2  # But not timeout

    def test_acquire_timeout(self):
        """Test timeout in blocking mode."""
        limiter = RateLimiter(requests_per_second=1, requests_per_day=1)

        # Fill capacity
        limiter.acquire(block=False)

        # Should timeout quickly
        with pytest.raises(EbayRateLimitError):
            limiter.acquire(block=True, timeout=0.1)

    def test_get_stats(self):
        """Test statistics retrieval."""
        limiter = RateLimiter(requests_per_second=10, requests_per_day=100)

        # Make some requests
        limiter.acquire(block=False)
        limiter.acquire(block=False)

        stats = limiter.get_stats()

        assert stats["per_second"]["used"] == 2
        assert stats["per_second"]["remaining"] == 8
        assert stats["per_day"]["used"] == 2
        assert stats["per_day"]["remaining"] == 98

    def test_reset(self):
        """Test resetting limiter."""
        limiter = RateLimiter(requests_per_second=2, requests_per_day=10)

        # Fill capacity
        limiter.acquire(block=False)
        limiter.acquire(block=False)

        # Reset
        limiter.reset()

        # Should work again
        result = limiter.acquire(block=False)
        assert result is True

    def test_thread_safety(self):
        """Test thread-safe operation."""
        limiter = RateLimiter(requests_per_second=100, requests_per_day=1000)

        results = []

        def make_request():
            try:
                limiter.acquire(block=False)
                results.append(True)
            except EbayRateLimitError:
                results.append(False)

        # Create threads
        threads = [Thread(target=make_request) for _ in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # All should succeed (well under limit)
        assert all(results)
