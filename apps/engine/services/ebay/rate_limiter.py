"""
eBay API rate limiting.

Prevents exceeding eBay's rate limits for API requests.
"""
import time
from collections import deque
from threading import Lock
from typing import Optional

from config import settings
from utils.logger import get_logger
from .exceptions import EbayRateLimitError

logger = get_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for eBay API requests.

    Enforces both per-second and per-day limits.
    Thread-safe implementation.
    """

    def __init__(
        self,
        requests_per_second: Optional[int] = None,
        requests_per_day: Optional[int] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Max requests per second
                (defaults to settings)
            requests_per_day: Max requests per day (defaults to settings)
        """
        self.requests_per_second = (
            requests_per_second or settings.ebay_rate_limit_per_second
        )
        self.requests_per_day = requests_per_day or settings.ebay_rate_limit_per_day

        # Per-second rate limiting (sliding window)
        self._second_window: deque = deque()
        self._second_lock = Lock()

        # Per-day rate limiting (rolling 24h window)
        self._day_window: deque = deque()
        self._day_lock = Lock()

        logger.info(
            f"Rate limiter initialized: "
            f"{self.requests_per_second}/sec, {self.requests_per_day}/day"
        )

    def acquire(self, block: bool = True, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to make an API request.

        Args:
            block: If True, wait until permission granted
            timeout: Max seconds to wait (only if block=True)

        Returns:
            True if permission granted, False if would exceed limits

        Raises:
            EbayRateLimitError: If rate limit exceeded and block=False
        """
        start_time = time.time()

        while True:
            # Check if we can proceed
            if self._can_proceed():
                self._record_request()
                return True

            # If not blocking, raise error
            if not block:
                raise EbayRateLimitError(
                    "Rate limit would be exceeded",
                    retry_after=int(self._get_retry_after()),
                )

            # Check timeout
            if timeout and (time.time() - start_time) >= timeout:
                raise EbayRateLimitError(
                    "Rate limit timeout exceeded",
                    retry_after=int(self._get_retry_after()),
                )

            # Wait and retry
            sleep_time = min(0.1, self._get_retry_after())
            logger.debug(f"Rate limit waiting {sleep_time:.2f}s")
            time.sleep(sleep_time)

    def _can_proceed(self) -> bool:
        """
        Check if request can proceed without exceeding limits.

        Returns:
            True if request can proceed
        """
        now = time.time()

        # Clean old entries and check per-second limit
        with self._second_lock:
            self._clean_window(self._second_window, now, window_seconds=1)
            if len(self._second_window) >= self.requests_per_second:
                return False

        # Clean old entries and check per-day limit
        with self._day_lock:
            self._clean_window(self._day_window, now, window_seconds=86400)
            if len(self._day_window) >= self.requests_per_day:
                return False

        return True

    def _record_request(self) -> None:
        """Record that a request was made."""
        now = time.time()

        with self._second_lock:
            self._second_window.append(now)

        with self._day_lock:
            self._day_window.append(now)

    def _clean_window(self, window: deque, now: float, window_seconds: int) -> None:
        """
        Remove timestamps outside the time window.

        Args:
            window: Deque of timestamps
            now: Current timestamp
            window_seconds: Window size in seconds
        """
        cutoff = now - window_seconds

        while window and window[0] < cutoff:
            window.popleft()

    def _get_retry_after(self) -> float:
        """
        Get suggested retry delay in seconds.

        Returns:
            Seconds to wait before retry
        """
        now = time.time()

        # Check per-second window
        with self._second_lock:
            if len(self._second_window) >= self.requests_per_second:
                oldest = self._second_window[0]
                retry_after = 1.0 - (now - oldest)
                if retry_after > 0:
                    return retry_after

        # Check per-day window
        with self._day_lock:
            if len(self._day_window) >= self.requests_per_day:
                oldest = self._day_window[0]
                retry_after = 86400.0 - (now - oldest)
                if retry_after > 0:
                    return retry_after

        return 0.1  # Default small delay

    def get_stats(self) -> dict:
        """
        Get current rate limit statistics.

        Returns:
            Dict with current usage stats
        """
        now = time.time()

        with self._second_lock:
            self._clean_window(self._second_window, now, 1)
            per_second_used = len(self._second_window)

        with self._day_lock:
            self._clean_window(self._day_window, now, 86400)
            per_day_used = len(self._day_window)

        return {
            "per_second": {
                "used": per_second_used,
                "limit": self.requests_per_second,
                "remaining": self.requests_per_second - per_second_used,
            },
            "per_day": {
                "used": per_day_used,
                "limit": self.requests_per_day,
                "remaining": self.requests_per_day - per_day_used,
            },
        }

    def reset(self) -> None:
        """Reset rate limiter (useful for testing)."""
        with self._second_lock:
            self._second_window.clear()

        with self._day_lock:
            self._day_window.clear()

        logger.debug("Rate limiter reset")
