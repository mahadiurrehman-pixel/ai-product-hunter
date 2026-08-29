"""
eBay listing database models.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    Text,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class EbayListing(Base, TimestampMixin):
    """
    eBay product listing data.

    Stores data from eBay Browse API responses.
    """

    __tablename__ = "ebay_listings"

    # eBay identifiers
    item_id = Column(String(100), nullable=False, index=True)
    item_web_url = Column(Text, nullable=True)

    # eBay marketplace (e.g. EBAY_US, EBAY_GB, EBAY_DE, EBAY_AU, EBAY_CA)
    marketplace = Column(
        String(20),
        nullable=False,
        default="EBAY_US",
        server_default="EBAY_US",
        index=True,
    )

    # Basic product info
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)

    # Pricing
    price_value = Column(Numeric(10, 2), nullable=False)
    price_currency = Column(String(3), nullable=False, default="USD")

    # Images
    image_url = Column(Text, nullable=True)
    additional_images = Column(JSON, nullable=True)

    # Category
    category_id = Column(String(50), nullable=True, index=True)
    category_name = Column(String(200), nullable=True)
    category_path = Column(Text, nullable=True)

    # Condition
    condition = Column(String(50), nullable=True)
    condition_description = Column(Text, nullable=True)

    # Seller information
    seller_username = Column(String(100), nullable=True)
    seller_feedback_percentage = Column(Numeric(5, 2), nullable=True)
    seller_feedback_score = Column(Integer, nullable=True)

    # Buying options
    buying_options = Column(JSON, nullable=True)

    # Shipping
    shipping_options = Column(JSON, nullable=True)

    # Location
    item_location = Column(JSON, nullable=True)

    # Product attributes
    product_brand = Column(String(100), nullable=True)
    product_mpn = Column(String(100), nullable=True)
    product_aspects = Column(JSON, nullable=True)

    # Availability
    estimated_available_quantity = Column(Integer, nullable=True)
    estimated_sold_quantity = Column(Integer, nullable=True)

    # Raw data
    raw_data = Column(JSON, nullable=False)

    # Cache control
    fetched_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    cache_expires_at = Column(DateTime, nullable=True)

    # Relationships
    matches = relationship(
        "ProductMatch",
        back_populates="ebay_listing",
        foreign_keys="ProductMatch.ebay_listing_id"
    )

    __table_args__ = (
        UniqueConstraint(
            "marketplace",
            "item_id",
            name="uq_ebay_marketplace_item",
        ),
        Index('idx_ebay_price', 'price_value'),
        Index('idx_ebay_category', 'category_id'),
        Index('idx_ebay_fetched', 'fetched_at'),
        Index('idx_ebay_marketplace_item', 'marketplace', 'item_id'),
    )

    @property
    def item_url(self) -> Optional[str]:
        """Convenience alias for item_web_url."""
        return self.item_web_url

    def __repr__(self) -> str:
        return (
            f"<EbayListing(id={self.id}, marketplace='{self.marketplace}', "
            f"item_id='{self.item_id}', title='{self.title[:50]}...')>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "item_id": self.item_id,
            "marketplace": self.marketplace,
            "title": self.title,
            "price": {
                "value": float(self.price_value) if self.price_value is not None else 0.0,
                "currency": self.price_currency
            },
            "image_url": self.image_url,
            "item_web_url": self.item_web_url,
            "item_url": self.item_web_url,
            "category": self.category_name,
            "condition": self.condition,
            "seller": {
                "username": self.seller_username,
                "feedback_percentage": (
                    float(self.seller_feedback_percentage)
                    if self.seller_feedback_percentage else None
                ),
                "feedback_score": self.seller_feedback_score,
            },
            "estimated_sold_quantity": self.estimated_sold_quantity,
            "fetched_at": (
                self.fetched_at.isoformat() if self.fetched_at else None
            ),
        }