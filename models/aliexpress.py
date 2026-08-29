"""
AliExpress product database models.
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, String, Float, Boolean, Integer
from sqlalchemy import Column, String, Numeric, DateTime, Text, JSON, Index
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class AliExpressListing(Base, TimestampMixin):
    """
    AliExpress product listing data.

    Stores data from AliExpress API (or mock adapter).
    """

    __tablename__ = "aliexpress_listings"

    # AliExpress identifiers
    product_id = Column(String(100), unique=True, nullable=False, index=True)
    product_url = Column(Text, nullable=False)

    # Basic product info
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    # Pricing
    price_value = Column(Numeric(10, 2), nullable=False)
    price_currency = Column(String(3), nullable=False, default="USD")
    original_price_value = Column(Numeric(10, 2), nullable=True)  # Before discount

    # Images
    image_url = Column(Text, nullable=True)
    additional_images = Column(JSON, nullable=True)

    # Category
    category_id = Column(String(50), nullable=True, index=True)
    category_name = Column(String(200), nullable=True)

    # Supplier/Store information
    store_name = Column(String(200), nullable=True)
    store_id = Column(String(100), nullable=True)
    store_url = Column(Text, nullable=True)

    # Ratings & Reviews
    rating_score = Column(Numeric(3, 2), nullable=True)  # e.g., 4.8
    review_count = Column(Integer, nullable=True)
    orders_count = Column(Integer, nullable=True)  # Total orders

    # Shipping
    shipping_options = Column(JSON, nullable=True)
    ships_from = Column(String(100), nullable=True)

    # Product attributes
    attributes = Column(JSON, nullable=True)
    variations = Column(JSON, nullable=True)  # Color, size options

    # Availability
    available_stock = Column(Integer, nullable=True)

    # Raw data
    raw_data = Column(JSON, nullable=False)

    # Cache control
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    cache_expires_at = Column(DateTime, nullable=True)

    # Data source
    source = Column(String(20), default="mock", nullable=False)  # mock, api, affiliate

    # Relationships
    matches = relationship(
        "ProductMatch",
        back_populates="aliexpress_listing",
        foreign_keys="ProductMatch.aliexpress_listing_id",
    )

    # Indexes
    __table_args__ = (
        Index("idx_ali_price", "price_value"),
        Index("idx_ali_category", "category_id"),
        Index("idx_ali_rating", "rating_score"),
        Index("idx_ali_fetched", "fetched_at"),
    )

    def __repr__(self) -> str:
        return f"<AliExpressListing(id={self.id}, product_id='{self.product_id}', title='{self.title[:50]}...')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "product_id": self.product_id,
            "title": self.title,
            "price": {
                "value": float(self.price_value),
                "currency": self.price_currency,
            },
            "image_url": self.image_url,
            "product_url": self.product_url,
            "store": {
                "name": self.store_name,
                "url": self.store_url,
            },
            "rating": {
                "score": float(self.rating_score) if self.rating_score else None,
                "review_count": self.review_count,
                "orders_count": self.orders_count,
            },
            "source": self.source,
            "fetched_at": self.fetched_at.isoformat() if self.fetched_at else None,
        }
