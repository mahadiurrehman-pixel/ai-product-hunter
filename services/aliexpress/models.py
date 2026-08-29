"""
AliExpress product data models.

These are runtime dataclasses for data flow between services.
The database model (AliExpressListing) is in models/aliexpress.py.

All data from the mock adapter is clearly labeled source="mock".
When real API is integrated, source will be "api" or "affiliate".
"""
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class AliExpressPrice:
    """Price information for an AliExpress product."""

    value: Decimal
    currency: str = "USD"
    original_value: Optional[Decimal] = None  # Before discount

    def to_dict(self) -> dict:
        return {
            "value": float(self.value),
            "currency": self.currency,
            "original_value": (
                float(self.original_value)
                if self.original_value
                else None
            ),
        }


@dataclass
class AliExpressStore:
    """Supplier/store information."""

    name: str
    store_id: Optional[str] = None
    url: Optional[str] = None
    positive_feedback_rate: Optional[float] = None  # 0-100

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "store_id": self.store_id,
            "url": self.url,
            "positive_feedback_rate": self.positive_feedback_rate,
        }


@dataclass
class AliExpressShipping:
    """Shipping option."""

    method: str              # e.g. "AliExpress Standard Shipping"
    cost: Decimal            # 0.00 = free
    currency: str = "USD"
    estimated_days_min: Optional[int] = None
    estimated_days_max: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "method": self.method,
            "cost": float(self.cost),
            "currency": self.currency,
            "estimated_days_min": self.estimated_days_min,
            "estimated_days_max": self.estimated_days_max,
        }


@dataclass
class AliExpressProduct:
    """
    AliExpress product data.

    Represents one product from AliExpress, whether from mock
    adapter or real API. The source field always indicates origin.

    DEMO MODE: When source="mock", all data is simulated.
    Do not use mock prices for real purchasing decisions.
    """

    # Required fields
    product_id: str
    title: str
    price: AliExpressPrice
    product_url: str
    source: str  # "mock" | "api" | "affiliate"

    # Optional fields
    image_url: Optional[str] = None
    store: Optional[AliExpressStore] = None

    # Ratings
    rating_score: Optional[float] = None   # 0.0 - 5.0
    review_count: Optional[int] = None
    orders_count: Optional[int] = None     # Total orders

    # Product details
    attributes: Dict[str, str] = field(default_factory=dict)
    shipping_options: List[AliExpressShipping] = field(default_factory=list)

    # Metadata
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_mock(self) -> bool:
        """Whether this product came from mock adapter."""
        return self.source == "mock"

    @property
    def demo_label(self) -> str:
        """Label to show when data is mock."""
        if self.is_mock:
            return "⚠️ DEMO DATA — Not real product"
        return ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization and DB storage."""
        return {
            "product_id": self.product_id,
            "title": self.title,
            "price": self.price.to_dict(),
            "product_url": self.product_url,
            "source": self.source,
            "image_url": self.image_url,
            "store": self.store.to_dict() if self.store else None,
            "rating_score": self.rating_score,
            "review_count": self.review_count,
            "orders_count": self.orders_count,
            "attributes": self.attributes,
            "shipping_options": [s.to_dict() for s in self.shipping_options],
            "fetched_at": self.fetched_at.isoformat(),
            "is_mock": self.is_mock,
            "demo_label": self.demo_label,
        }

    def to_db_dict(self) -> dict:
        """
        Convert to dict matching AliExpressListing database model fields.
        """
        return {
            "product_id": self.product_id,
            "title": self.title,
            "price_value": self.price.value,
            "price_currency": self.price.currency,
            "original_price_value": self.price.original_value,
            "image_url": self.image_url,
            "store_name": self.store.name if self.store else None,
            "store_id": self.store.store_id if self.store else None,
            "store_url": self.store.url if self.store else None,
            "rating_score": self.rating_score,
            "review_count": self.review_count,
            "orders_count": self.orders_count,
            "attributes": self.attributes,
            "shipping_options": [
                s.to_dict() for s in self.shipping_options
            ],
            "source": self.source,
            "fetched_at": self.fetched_at,
            "product_url": self.product_url,
            "raw_data": self.to_dict(),
        }