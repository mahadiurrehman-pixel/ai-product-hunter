"""
Custom exception hierarchy for AI Product Hunter.
"""
from typing import Any, Dict, Optional


class ProductHunterError(Exception):
    """Base exception for all Product Hunter errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize exception.

        Args:
            message: Error message
            error_code: Machine-readable error code
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# =============================================================================
# API Errors
# =============================================================================


class APIError(ProductHunterError):
    """Base class for API-related errors."""

    pass


class EbayAPIError(APIError):
    """eBay API specific errors."""

    pass


class AliExpressAPIError(APIError):
    """AliExpress API specific errors."""

    pass


class AuthenticationError(APIError):
    """Authentication/authorization errors."""

    pass


class RateLimitError(APIError):
    """Rate limit exceeded errors."""

    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        """
        Initialize rate limit error.

        Args:
            message: Error message
            retry_after: Seconds until retry is allowed
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.retry_after = retry_after
        if retry_after:
            self.details["retry_after"] = retry_after


# =============================================================================
# Database Errors
# =============================================================================


class DatabaseError(ProductHunterError):
    """Database operation errors."""

    pass


# =============================================================================
# Validation Errors
# =============================================================================


class ValidationError(ProductHunterError):
    """Input validation errors."""

    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        """
        Initialize validation error.

        Args:
            message: Error message
            field: Field that failed validation
            **kwargs: Additional arguments
        """
        super().__init__(message, **kwargs)
        self.field = field
        if field:
            self.details["field"] = field


# =============================================================================
# Cache Errors
# =============================================================================


class CacheError(ProductHunterError):
    """Cache operation errors."""

    pass


# =============================================================================
# Matching Errors
# =============================================================================


class MatchingError(ProductHunterError):
    """Product matching errors."""

    pass


# =============================================================================
# Configuration Errors
# =============================================================================


class ConfigurationError(ProductHunterError):
    """Configuration errors."""

    pass
