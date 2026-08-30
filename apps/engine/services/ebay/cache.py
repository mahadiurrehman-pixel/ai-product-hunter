"""
eBay API caching layer with retry, deduplication, and monitoring.

Provides cache-first data retrieval using the existing SQLite database.
Includes:
- TTL-based freshness checking
- Exponential backoff retry for transient failures
- In-process request deduplication
- Query normalization
- Structured cache/retry logging
- Stale data fallback on API failure

Does NOT cache OAuth tokens (already handled by EbayAuth).
Does NOT introduce Redis or external cache infrastructure.
"""
import hashlib
import json
import re
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from config import settings
from models.ebay import EbayListing
from utils.logger import get_logger

logger = get_logger(__name__)


def is_fresh(
    fetched_at: Optional[datetime],
    ttl_seconds: int,
    now: Optional[datetime] = None,
) -> bool:
    """
    Determine whether cached data is still fresh.

    Args:
        fetched_at: When the data was last fetched (UTC)
        ttl_seconds: Time-to-live in seconds
        now: Current time (UTC). Injectable for testing.

    Returns:
        True if data is fresh (fetched_at + TTL > now)
    """
    if fetched_at is None:
        return False

    if now is None:
        now = datetime.now(timezone.utc)

    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    age = (now - fetched_at).total_seconds()
    return age < ttl_seconds


def normalize_query(query: str) -> str:
    """
    Normalize a search query for consistent cache key generation.

    Normalization steps:
    1. Strip leading/trailing whitespace
    2. Lowercase
    3. Collapse repeated whitespace
    4. Remove leading/trailing punctuation

    Does NOT remove meaningful search terms (numbers, model names, etc.).

    Args:
        query: Raw search query

    Returns:
        Normalized query string
    """
    if not query:
        return ""

    # Strip whitespace
    q = query.strip()

    # Lowercase
    q = q.lower()

    # Collapse repeated whitespace
    q = re.sub(r"\s+", " ", q)

    # Strip leading/trailing punctuation (but keep internal punctuation)
    q = q.strip(".,;:!?")

    return q


def generate_search_cache_key(
    query: str,
    marketplace: str,
    limit: int = 50,
    offset: int = 0,
    category_id: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    condition: Optional[str] = None,
    sort: str = "relevance",
) -> str:
    """
    Generate a deterministic cache key for a search request.

    Uses SHA-256 hash of normalized parameters.
    Deterministic across application restarts.

    Args:
        query: Search query string (will be normalized)
        marketplace: eBay marketplace ID
        limit: Results per page
        offset: Pagination offset
        category_id: Category filter
        min_price: Minimum price filter
        max_price: Maximum price filter
        condition: Condition filter
        sort: Sort order

    Returns:
        Deterministic SHA-256 hex cache key
    """
    normalized_q = normalize_query(query)

    key_data = {
        "q": normalized_q,
        "marketplace": marketplace.upper(),
        "limit": limit,
        "offset": offset,
        "category_id": category_id or "",
        "min_price": min_price,
        "max_price": max_price,
        "condition": (condition or "").upper(),
        "sort": sort.lower(),
    }

    serialized = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


class EbayCacheService:
    """
    Cache-first service for eBay data retrieval.

    Features:
    - Cache-first with TTL freshness
    - Exponential backoff retry for transient failures
    - In-process request deduplication
    - Stale data fallback on API failure
    - Structured logging

    Usage:
        cache_service = EbayCacheService()
        results = cache_service.search_items("wireless earbuds", limit=20)
    """

    def __init__(self, ebay_client=None):
        """
        Initialize cache service.

        Args:
            ebay_client: EbayClient instance. Creates new if None.
        """
        if ebay_client is None:
            from .client import EbayClient
            self._client = EbayClient()
        else:
            self._client = ebay_client

        self._search_ttl = settings.ebay_search_cache_ttl_seconds
        self._item_ttl = settings.ebay_item_cache_ttl_seconds

        # Retry configuration
        self._max_retries = settings.ebay_max_retries
        self._retry_base_delay = settings.ebay_retry_base_delay_seconds
        self._retry_max_delay = settings.ebay_retry_max_delay_seconds

        # In-process request deduplication
        self._inflight_lock = threading.Lock()
        self._inflight: Dict[str, threading.Event] = {}
        self._inflight_results: Dict[str, Optional[dict]] = {}

    @property
    def search_ttl_seconds(self) -> int:
        return self._search_ttl

    @property
    def item_ttl_seconds(self) -> int:
        return self._item_ttl

    def search_items(
        self,
        query: str,
        limit: int = 50,
        offset: int = 0,
        category_id: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        condition: Optional[str] = None,
        sort: str = "relevance",
        db: Optional[Session] = None,
    ) -> dict:
        """
        Search eBay items with cache-first strategy.

        Flow:
        1. Generate cache key from normalized parameters
        2. Check database for fresh cached results
        3. If fresh → return cached (log CACHE_HIT, no API call)
        4. If stale/missing → check in-flight dedup
        5. If not in-flight → call eBay API with retry
        6. On success → update cache, return
        7. On failure → return stale fallback if available, else raise
        """
        cache_key = generate_search_cache_key(
            query=query,
            marketplace=self._client.marketplace_id,
            limit=limit,
            offset=offset,
            category_id=category_id,
            min_price=min_price,
            max_price=max_price,
            condition=condition,
            sort=sort,
        )

        # Step 1: Check cache
        cached = self._get_cached_search(cache_key, db=db)

        if cached is not None:
            logger.info(
                f"EBAY_CACHE_HIT: query='{normalize_query(query)}', "
                f"marketplace={self._client.marketplace_id}, "
                f"items={len(cached.get('items', []))}"
            )
            self._log_cache_event("CACHE_HIT", cache_key, db)
            return cached

        logger.info(
            f"EBAY_CACHE_MISS: query='{normalize_query(query)}', "
            f"marketplace={self._client.marketplace_id}"
        )
        self._log_cache_event("CACHE_MISS", cache_key, db)

        # Step 2: In-process deduplication
        dedup_result = self._wait_for_inflight(cache_key)
        if dedup_result is not None:
            logger.info(
                f"EBAY_REQUEST_DEDUPLICATED: "
                f"query='{normalize_query(query)}'"
            )
            return dedup_result

        # Step 3: Mark as in-flight
        self._mark_inflight(cache_key)

        try:
            # Step 4: Call API with retry
            results = self._call_with_retry(
                lambda: self._client.search_items(
                    query=query,
                    limit=limit,
                    offset=offset,
                    category_id=category_id,
                    min_price=min_price,
                    max_price=max_price,
                    condition=condition,
                    sort=sort,
                ),
                context=f"search '{normalize_query(query)}'",
            )

            # Step 5: Cache results
            self._cache_search_results(cache_key, results, db=db)
            self._store_inflight_result(cache_key, results)

            return results

        except Exception as e:
            logger.error(
                f"EBAY_API_FAILURE: query='{normalize_query(query)}': {e}"
            )
            self._store_inflight_result(cache_key, None)

            # Try stale fallback
            stale = self._get_cached_search(
                cache_key, db=db, ignore_freshness=True
            )
            if stale is not None:
                logger.warning(
                    f"EBAY_CACHE_STALE fallback: "
                    f"query='{normalize_query(query)}'"
                )
                self._log_cache_event("CACHE_STALE", cache_key, db)
                return stale
            raise

        finally:
            self._clear_inflight(cache_key)

    def get_item_details(
        self,
        item_id: str,
        db: Optional[Session] = None,
    ) -> dict:
        """
        Get item details with cache-first strategy and retry.
        """
        cached = self._get_cached_item(item_id, db=db)

        if cached is not None:
            logger.info(f"EBAY_CACHE_HIT: item_id={item_id}")
            return cached

        logger.info(f"EBAY_CACHE_MISS: item_id={item_id}")

        try:
            result = self._call_with_retry(
                lambda: self._client.get_item_details(item_id),
                context=f"item {item_id}",
            )
            self._cache_item_details(result, db=db)
            return result

        except Exception as e:
            logger.error(f"EBAY_API_FAILURE: item_id={item_id}: {e}")
            stale = self._get_cached_item(
                item_id, db=db, ignore_freshness=True
            )
            if stale is not None:
                logger.warning(
                    f"EBAY_CACHE_STALE fallback: item_id={item_id}"
                )
                return stale
            raise

    def _call_with_retry(self, api_call, context: str = ""):
        """
        Call an API function with exponential backoff retry.

        Retries only transient failures:
        - HTTP 429 (rate limit)
        - HTTP 5xx (server errors)
        - Network/timeout errors

        Does NOT retry:
        - HTTP 401 (auth failure)
        - HTTP 404 (not found)
        - HTTP 400 (bad request)
        - Other 4xx errors

        Args:
            api_call: Callable that makes the API request
            context: Description for logging

        Returns:
            API call result

        Raises:
            Original exception if all retries exhausted
        """
        from services.ebay.exceptions import (
            EbayRateLimitError,
            EbayNetworkError,
            EbayAPIError,
            EbayAuthenticationError,
        )

        last_exception = None

        for attempt in range(1, self._max_retries + 1):
            try:
                result = api_call()
                if attempt > 1:
                    logger.info(
                        f"EBAY_API_RETRY_SUCCESS: {context} "
                        f"(attempt {attempt})"
                    )
                return result

            except EbayRateLimitError as e:
                last_exception = e
                delay = self._calculate_backoff(attempt)
                logger.warning(
                    f"EBAY_RATE_LIMIT: {context} "
                    f"(attempt {attempt}/{self._max_retries}, "
                    f"retry in {delay:.1f}s)"
                )
                time.sleep(delay)

            except EbayNetworkError as e:
                last_exception = e
                delay = self._calculate_backoff(attempt)
                logger.warning(
                    f"EBAY_API_RETRY: {context} "
                    f"(attempt {attempt}/{self._max_retries}, "
                    f"network error, retry in {delay:.1f}s)"
                )
                time.sleep(delay)

            except EbayAPIError as e:
                # Check if it's a retryable server error
                status = e.details.get("status_code", 0)
                if status >= 500:
                    last_exception = e
                    delay = self._calculate_backoff(attempt)
                    logger.warning(
                        f"EBAY_API_RETRY: {context} "
                        f"(attempt {attempt}/{self._max_retries}, "
                        f"HTTP {status}, retry in {delay:.1f}s)"
                    )
                    time.sleep(delay)
                else:
                    # Permanent error — don't retry
                    raise

            except EbayAuthenticationError:
                # Auth errors are permanent — don't retry
                raise

        # All retries exhausted
        logger.error(
            f"EBAY_API_FAILURE: {context} "
            f"({self._max_retries} retries exhausted)"
        )
        raise last_exception

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.

        Formula: min(base_delay * 2^(attempt-1), max_delay)

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds
        """
        delay = self._retry_base_delay * (2 ** (attempt - 1))
        return min(delay, self._retry_max_delay)

    # =========================================================================
    # In-process request deduplication
    # =========================================================================

    def _mark_inflight(self, cache_key: str) -> None:
        """Mark a request as in-flight for deduplication."""
        with self._inflight_lock:
            if cache_key not in self._inflight:
                self._inflight[cache_key] = threading.Event()
                self._inflight_results[cache_key] = None

    def _wait_for_inflight(
        self, cache_key: str, timeout: float = 30.0
    ) -> Optional[dict]:
        """
        Wait for an in-flight request to complete.

        Returns cached result if another thread is already fetching
        the same data. Returns None if no in-flight request exists.
        """
        with self._inflight_lock:
            event = self._inflight.get(cache_key)
            if event is None:
                return None

        # Another thread is fetching this data — wait for it
        logger.debug(
            f"EBAY_REQUEST_DEDUPLICATED: waiting for in-flight "
            f"request {cache_key[:16]}..."
        )
        event.wait(timeout=timeout)

        with self._inflight_lock:
            result = self._inflight_results.get(cache_key)
        return result

    def _store_inflight_result(
        self, cache_key: str, result: Optional[dict]
    ) -> None:
        """Store result for waiting threads."""
        with self._inflight_lock:
            self._inflight_results[cache_key] = result
            event = self._inflight.get(cache_key)
            if event:
                event.set()

    def _clear_inflight(self, cache_key: str) -> None:
        """Clear in-flight tracking for a cache key."""
        with self._inflight_lock:
            self._inflight.pop(cache_key, None)
            self._inflight_results.pop(cache_key, None)

    # =========================================================================
    # Cache lookup and storage
    # =========================================================================

    def _get_cached_search(
        self,
        cache_key: str,
        db: Optional[Session] = None,
        ignore_freshness: bool = False,
    ) -> Optional[dict]:
        """Check database for cached search results."""
        close_db = False
        if db is None:
            from database import get_db as _get_db
            db = next(_get_db())
            close_db = True

        try:
            now = datetime.now(timezone.utc)
            query = db.query(EbayListing).filter(
                EbayListing.marketplace == self._client.marketplace_id
            )

            if not ignore_freshness:
                cutoff = now - timedelta(seconds=self._search_ttl)
                query = query.filter(EbayListing.fetched_at >= cutoff)

            listings = query.limit(200).all()

            if not listings:
                return None

            items = [listing.to_dict() for listing in listings]

            return {
                "total": len(items),
                "limit": len(items),
                "offset": 0,
                "items": items,
                "items_count": len(items),
                "marketplace": self._client.marketplace_id,
                "cached": True,
                "cache_key": cache_key,
            }
        finally:
            if close_db:
                db.close()

    def _get_cached_item(
        self,
        item_id: str,
        db: Optional[Session] = None,
        ignore_freshness: bool = False,
    ) -> Optional[dict]:
        """Check database for a cached item by item_id."""
        close_db = False
        if db is None:
            from database import get_db as _get_db
            db = next(_get_db())
            close_db = True

        try:
            from .repository import EbayListingRepository
            listing = EbayListingRepository.get_by_item_id(db, item_id)

            if listing is None:
                return None

            if not ignore_freshness:
                now = datetime.now(timezone.utc)
                if not is_fresh(listing.fetched_at, self._item_ttl, now):
                    logger.info(f"EBAY_CACHE_STALE: item_id={item_id}")
                    return None

            result = listing.to_dict()
            result["cached"] = True
            return result
        finally:
            if close_db:
                db.close()

    def _cache_search_results(
        self,
        cache_key: str,
        results: dict,
        db: Optional[Session] = None,
    ) -> None:
        """Cache search results to database."""
        from .repository import EbayListingRepository

        close_db = False
        if db is None:
            from database import get_db as _get_db
            db = next(_get_db())
            close_db = True

        try:
            items = results.get("items", [])
            saved = EbayListingRepository.save_listings_bulk(db, items)
            logger.info(
                f"EBAY_CACHE_UPDATE: {len(saved)} items "
                f"for key={cache_key[:16]}..."
            )
        except Exception as e:
            logger.warning(f"Failed to cache search results: {e}")
        finally:
            if close_db:
                db.close()

    def _cache_item_details(
        self, result: dict, db: Optional[Session] = None
    ) -> None:
        """Cache item details to database."""
        from .repository import EbayListingRepository

        close_db = False
        if db is None:
            from database import get_db as _get_db
            db = next(_get_db())
            close_db = True

        try:
            EbayListingRepository.save_listing(db, result)
            logger.info(
                f"EBAY_CACHE_UPDATE: item_id={result.get('item_id')}"
            )
        except Exception as e:
            logger.warning(f"Failed to cache item details: {e}")
        finally:
            if close_db:
                db.close()

    def _log_cache_event(
        self,
        event_type: str,
        cache_key: str,
        db: Optional[Session] = None,
    ) -> None:
        """Log a cache event to APIRequestLog."""
        close_db = False
        if db is None:
            from database import get_db as _get_db
            db = next(_get_db())
            close_db = True

        try:
            from models.audit import APIRequestLog

            is_hit = event_type == "CACHE_HIT"
            log_entry = APIRequestLog(
                service="ebay",
                endpoint="cache",
                method="CACHE",
                status_code=200 if is_hit else None,
                was_cached=is_hit,
                cache_key=cache_key,
                error_occurred=(event_type == "CACHE_STALE"),
                error_message=event_type,
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to log cache event: {e}")
        finally:
            if close_db:
                db.close()