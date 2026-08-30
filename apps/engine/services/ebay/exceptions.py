"""
eBay service-specific exceptions.
"""
from typing import Any, Dict, Optional
from utils.exceptions import APIError


class EbayServiceError(APIError):
    """Base exception for eBay service errors."""

    pass


class EbayAuthenticationError(EbayServiceError):
    """eBay authentication/authorization errors."""

    def __init__(
        self,
        message: str = "eBay authentication failed",
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code or "EBAY_AUTH_ERROR",
            details=details,
        )


class EbayRateLimitError(EbayServiceError):
    """eBay rate limit exceeded."""

    def __init__(
        self,
        message: str = "eBay API rate limit exceeded",
        retry_after: Optional[int] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        if retry_after:
            self.details["retry_after"] = retry_after
            self.details["retry_after_human"] = f"{retry_after} seconds"


class EbayAPIError(EbayServiceError):
    """eBay API request/response errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        if status_code:
            self.details["status_code"] = status_code
        if response_body:
            self.details["response_body"] = response_body


class EbayInvalidResponseError(EbayServiceError):
    """Invalid or malformed eBay API response."""

    def __init__(
        self,
        message: str = "Invalid eBay API response format",
        field: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(message, **kwargs)
        if field:
            self.details["field"] = field


class EbayNetworkError(EbayServiceError):
    """Network/connectivity errors."""

    pass
