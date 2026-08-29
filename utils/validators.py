"""
Input validation utilities.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Optional

from .exceptions import ValidationError


def validate_search_query(query: str) -> str:
    """
    Validate search query string.

    Args:
        query: Search query

    Returns:
        Cleaned query string

    Raises:
        ValidationError: If query is invalid
    """
    if not query or not query.strip():
        raise ValidationError("Search query cannot be empty", field="query")

    cleaned = query.strip()

    if len(cleaned) < 2:
        raise ValidationError(
            "Search query must be at least 2 characters", field="query"
        )

    if len(cleaned) > 200:
        raise ValidationError(
            "Search query cannot exceed 200 characters", field="query"
        )

    return cleaned


def validate_price(price: float, field_name: str = "price") -> Decimal:
    """
    Validate and convert price to Decimal.

    Args:
        price: Price value
        field_name: Field name for error messages

    Returns:
        Validated price as Decimal

    Raises:
        ValidationError: If price is invalid
    """
    try:
        price_decimal = Decimal(str(price))
    except (InvalidOperation, ValueError):
        raise ValidationError(f"Invalid {field_name} format", field=field_name)

    if price_decimal < 0:
        raise ValidationError(f"{field_name} cannot be negative", field=field_name)

    if price_decimal > 1000000:
        raise ValidationError(
            f"{field_name} exceeds maximum allowed value", field=field_name
        )

    return price_decimal


def validate_limit(limit: int, max_limit: int = 200) -> int:
    """
    Validate pagination limit.

    Args:
        limit: Requested limit
        max_limit: Maximum allowed limit

    Returns:
        Validated limit

    Raises:
        ValidationError: If limit is invalid
    """
    if not isinstance(limit, int):
        raise ValidationError("Limit must be an integer", field="limit")

    if limit < 1:
        raise ValidationError("Limit must be at least 1", field="limit")

    if limit > max_limit:
        raise ValidationError(f"Limit cannot exceed {max_limit}", field="limit")

    return limit


def validate_offset(offset: int) -> int:
    """
    Validate pagination offset.

    Args:
        offset: Requested offset

    Returns:
        Validated offset

    Raises:
        ValidationError: If offset is invalid
    """
    if not isinstance(offset, int):
        raise ValidationError("Offset must be an integer", field="offset")

    if offset < 0:
        raise ValidationError("Offset cannot be negative", field="offset")

    return offset


def validate_score(score: float, field_name: str = "score") -> float:
    """
    Validate score is between 0 and 100.

    Args:
        score: Score value
        field_name: Field name for error messages

    Returns:
        Validated score

    Raises:
        ValidationError: If score is invalid
    """
    if not isinstance(score, (int, float)):
        raise ValidationError(f"{field_name} must be a number", field=field_name)

    if not 0 <= score <= 100:
        raise ValidationError(
            f"{field_name} must be between 0 and 100", field=field_name
        )

    return float(score)


def validate_ebay_item_id(item_id: str) -> str:
    """
    Validate eBay item ID format.

    Args:
        item_id: eBay item ID

    Returns:
        Validated item ID

    Raises:
        ValidationError: If item ID is invalid
    """
    if not item_id or not item_id.strip():
        raise ValidationError("eBay item ID cannot be empty", field="item_id")

    # eBay item IDs from Browse API are in format: v1|123456789|0
    # Also accept legacy numeric IDs
    if not re.match(r"^(v1\|\d+\|\d+|\d+)$", item_id):
        raise ValidationError("Invalid eBay item ID format", field="item_id")

    return item_id


def validate_currency(currency: str) -> str:
    """
    Validate currency code.

    Args:
        currency: ISO currency code

    Returns:
        Uppercase currency code

    Raises:
        ValidationError: If currency is invalid
    """
    if not currency or not currency.strip():
        raise ValidationError("Currency code cannot be empty", field="currency")

    currency_upper = currency.strip().upper()

    # Basic validation - 3 letter code
    if not re.match(r"^[A-Z]{3}$", currency_upper):
        raise ValidationError(
            "Currency code must be 3 letters (ISO 4217)", field="currency"
        )

    return currency_upper
