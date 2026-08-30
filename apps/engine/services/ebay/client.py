"""
eBay Browse API client.

Official documentation:
https://developer.ebay.com/api-docs/buy/browse/overview.html

Supports multiple regional eBay marketplaces through the
EbayMarketplace enum. The marketplace can be provided at
construction time or read from settings.
"""
from typing import Any, Dict, Optional
from datetime import datetime

import httpx
from database.connection import get_db_context
from models.audit import APIRequestLog
from config import settings
from utils.logger import get_logger
from utils.validators import (
    validate_search_query,
    validate_limit,
    validate_offset,
)
from models.audit import APIRequestLog
from database import get_db
from .auth import EbayAuth
from .parser import EbayParser
from .rate_limiter import RateLimiter
from .marketplace import EbayMarketplace
from .exceptions import (
    EbayAPIError,
    EbayRateLimitError,
    EbayAuthenticationError,
    EbayNetworkError,
    EbayInvalidResponseError,
)

logger = get_logger(__name__)


class EbayClient:
    """
    eBay Browse API client.

    Single client implementation supporting all regional eBay marketplaces.
    The active marketplace is determined by (in order):
    1. `marketplace` argument passed to constructor
    2. `settings.ebay_marketplace` (from EBAY_MARKETPLACE_ID env var)

    Example:
        # Use configured marketplace (from .env)
        client = EbayClient()

        # Explicitly target UK marketplace
        client = EbayClient(marketplace=EbayMarketplace.UK)

        # All calls will use the selected marketplace's
        # X-EBAY-C-MARKETPLACE-ID header
        results = client.search_items("wireless earbuds")
    """

    def __init__(
        self,
        auth: Optional[EbayAuth] = None,
        rate_limiter: Optional[RateLimiter] = None,
        parser: Optional[EbayParser] = None,
        marketplace: Optional[EbayMarketplace] = None,
    ):
        """
        Initialize eBay client.

        Args:
            auth: eBay authentication manager (default: create new)
            rate_limiter: Rate limiter instance (default: create new)
            parser: Response parser (default: use EbayParser)
            marketplace: eBay marketplace to use (default: from settings)
        """
        self.auth = auth or EbayAuth()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.parser = parser or EbayParser()

        self.base_url = settings.ebay_api_base_url

        # Resolve marketplace: explicit arg > settings default
        self.marketplace = marketplace or settings.ebay_marketplace

        logger.info(
            f"EbayClient initialized: marketplace={self.marketplace.value} "
            f"({self.marketplace.display_name}), "
            f"environment={settings.ebay_environment}"
        )

    @property
    def marketplace_id(self) -> str:
        """
        Get the marketplace ID string for API headers.

        Kept as a property (not just a stored value) so the
        marketplace can be swapped at runtime if needed.

        Returns:
            Marketplace ID string (e.g., "EBAY_US")
        """
        return self.marketplace.value

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
    ) -> dict:
        """
        Search eBay items using Browse API.

        Endpoint: GET /buy/browse/v1/item_summary/search

        Args:
            query: Search keywords
            limit: Max items to return (1-200)
            offset: Pagination offset
            category_id: Filter by category ID
            min_price: Minimum price filter
            max_price: Maximum price filter
            condition: Item condition (NEW, USED, etc.)
            sort: Sort order (relevance, price, newlyListed)

        Returns:
            Parsed search results with items and metadata.
            Each item in "items" list has a "marketplace" field
            injected identifying the source marketplace.

        Raises:
            EbayAPIError: If API request fails
            EbayRateLimitError: If rate limit exceeded
            EbayAuthenticationError: If authentication fails
        """
        # Validate inputs
        query = validate_search_query(query)
        limit = validate_limit(limit, max_limit=200)
        offset = validate_offset(offset)

        # Build query parameters
        params = {
            "q": query,
            "limit": limit,
            "offset": offset,
            "sort": sort,
        }

        # Add optional filters
        filters = []

        if category_id:
            params["category_ids"] = category_id

        if min_price is not None or max_price is not None:
            price_filter = "price:["
            price_filter += str(min_price) if min_price is not None else ""
            price_filter += ".."
            price_filter += str(max_price) if max_price is not None else ""
            price_filter += "]"
            filters.append(price_filter)

        if condition:
            filters.append(f"conditions:{{{condition}}}")

        if filters:
            params["filter"] = ",".join(filters)

        # Make API request
        endpoint = "/buy/browse/v1/item_summary/search"

        logger.info(
            f"eBay search on {self.marketplace.value}: "
            f"query='{query}', limit={limit}, offset={offset}"
        )

        response_data = self._make_request(
            method="GET",
            endpoint=endpoint,
            params=params,
        )

        # Parse response and inject marketplace into each item
        try:
            parsed = self.parser.parse_search_response(
                response_data,
                marketplace=self.marketplace.value,
            )
            logger.info(
                f"eBay search on {self.marketplace.value} successful: "
                f"{parsed['items_count']} items"
            )
            # Also add marketplace to top-level response for callers
            parsed["marketplace"] = self.marketplace.value
            return parsed

        except Exception as e:
            logger.error(f"Failed to parse eBay search response: {e}")
            raise EbayInvalidResponseError(
                f"Failed to parse search response: {str(e)}"
            )

    def get_item_details(self, item_id: str) -> dict:
        """
        Get detailed information for specific item.

        Endpoint: GET /buy/browse/v1/item/{item_id}

        Args:
            item_id: eBay item ID

        Returns:
            Parsed item details with marketplace field injected.

        Raises:
            EbayAPIError: If API request fails
        """
        from utils.validators import validate_ebay_item_id

        item_id = validate_ebay_item_id(item_id)

        endpoint = f"/buy/browse/v1/item/{item_id}"

        logger.info(
            f"Fetching eBay item details on {self.marketplace.value}: "
            f"{item_id}"
        )

        response_data = self._make_request(
            method="GET",
            endpoint=endpoint,
        )

        try:
            parsed = self.parser.parse_item_details(
                response_data,
                marketplace=self.marketplace.value,
            )
            logger.info(
                f"eBay item details retrieved on "
                f"{self.marketplace.value}: {item_id}"
            )
            return parsed

        except Exception as e:
            logger.error(f"Failed to parse item details: {e}")
            raise EbayInvalidResponseError(
                f"Failed to parse item details: {str(e)}"
            )

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """
        Make authenticated request to eBay API.

        Uses the configured marketplace ID in the
        X-EBAY-C-MARKETPLACE-ID header per eBay Browse API spec.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON body data

        Returns:
            Response JSON data
        """
        # Acquire rate limit permission
        try:
            self.rate_limiter.acquire(block=True, timeout=30)
        except EbayRateLimitError as e:
            logger.warning(f"Rate limit exceeded: {e}")
            raise

        # Get access token
        try:
            access_token = self.auth.get_application_token()
        except EbayAuthenticationError as e:
            logger.error(f"Authentication failed: {e}")
            raise

        # Build headers — marketplace comes from configured enum
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            "Accept": "application/json",
        }

        url = f"{self.base_url}{endpoint}"
        request_start = datetime.utcnow()

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                )

                request_duration = (
                    datetime.utcnow() - request_start
                ).total_seconds()

                self._log_request(
                    endpoint=endpoint,
                    method=method,
                    status_code=response.status_code,
                    response_time_ms=int(request_duration * 1000),
                    error_occurred=response.status_code >= 400,
                )

                self._handle_response_errors(response)

                try:
                    return response.json()
                except Exception as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    raise EbayInvalidResponseError(
                        "Invalid JSON response from eBay API"
                    )

        except httpx.TimeoutException as e:
            logger.error(f"eBay API timeout: {e}")
            self._log_request(
                endpoint=endpoint,
                method=method,
                error_occurred=True,
                error_message="Request timeout",
            )
            raise EbayNetworkError(f"Request timeout: {str(e)}")

        except httpx.RequestError as e:
            logger.error(f"eBay API network error: {e}")
            self._log_request(
                endpoint=endpoint,
                method=method,
                error_occurred=True,
                error_message=f"Network error: {str(e)}",
            )
            raise EbayNetworkError(f"Network error: {str(e)}")

    def _handle_response_errors(self, response: httpx.Response) -> None:
        """
        Handle HTTP response errors.
        """
        if response.status_code == 200:
            return

        if response.status_code == 401:
            logger.error("eBay API returned 401 Unauthorized")
            raise EbayAuthenticationError(
                "Unauthorized - invalid or expired token",
                details={"status_code": 401},
            )

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            logger.warning(
                f"eBay API rate limit: retry after {retry_after}s"
            )
            raise EbayRateLimitError(
                "Rate limit exceeded",
                retry_after=int(retry_after) if retry_after else 60,
            )

        if response.status_code == 404:
            raise EbayAPIError(
                "Resource not found",
                status_code=404,
            )

        if response.status_code >= 500:
            logger.error(f"eBay API server error: {response.status_code}")
            raise EbayAPIError(
                f"eBay API server error: {response.status_code}",
                status_code=response.status_code,
                response_body=response.text[:500],
            )

        logger.error(f"eBay API error: {response.status_code}")
        raise EbayAPIError(
            f"eBay API request failed: {response.status_code}",
            status_code=response.status_code,
            response_body=response.text[:500],
        )

# FIND this pattern in services/ebay/client.py:
#
#     def _log_request(self, ...):
#         db = next(get_db())
#         try:
#             log_entry = APIRequestLog(...)
#             db.add(log_entry)
#             db.commit()
#         except Exception as e:
#             logger.warning(f"Failed to log API request: {e}")
#         finally:
#             db.close()
#
    def _log_request(
        self,
        endpoint: str = "",
        method: str = "GET",
        status_code: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        error_occurred: bool = False,
        error_message: Optional[str] = None,
        service: str = "ebay_browse",
        was_cached: bool = False,
        cache_key: str = "",
        **kwargs: Any,
    ) -> None:
        """
        Log an API request to the audit table.

        Stores method and endpoint as separate fields.
        Uses get_db_context() for proper session lifecycle.
        Failures are logged but never raise.
        """
        try:
            from database.connection import get_db_context
            from models.audit import APIRequestLog

            # Normalize: extract method from endpoint if embedded
            clean_method = method.upper() if method else "GET"
            clean_endpoint = endpoint

            # If endpoint contains method prefix (e.g. "GET /buy/..."), strip it
            parts = endpoint.strip().split(" ", 1)
            if len(parts) == 2 and parts[0].upper() in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                clean_method = parts[0].upper()
                clean_endpoint = parts[1]

            effective_status = (
                status_code if status_code is not None
                else (500 if error_occurred else 200)
            )

            with get_db_context() as db:
                log_entry = APIRequestLog(
                    service=service,
                    endpoint=clean_endpoint,
                    method=clean_method,
                    status_code=effective_status,
                    response_time_ms=float(response_time_ms or 0),
                    was_cached=was_cached,
                    cache_key=cache_key or None,
                    error_occurred=error_occurred,
                    error_message=error_message,
                    error_type=kwargs.get("error_type"),
                    request_params=str(kwargs.get("params", ""))[:500] if kwargs.get("params") else None,
                )
                db.add(log_entry)
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to log API request: {e}")