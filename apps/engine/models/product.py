"""
Normalized product database models.
"""
from sqlalchemy import Column, String, Text, JSON, Integer

from .base import Base, TimestampMixin


class NormalizedProduct(Base, TimestampMixin):
    """
    Normalized product representation.

    Stores cleaned/normalized product data for better matching.
    """

    __tablename__ = "normalized_products"

    # Normalized fields
    normalized_title = Column(Text, nullable=False, index=True)
    brand = Column(String(100), nullable=True, index=True)
    category = Column(String(200), nullable=True, index=True)
    product_type = Column(String(100), nullable=True)

    # Extracted attributes
    attributes = Column(JSON, nullable=True)
    # Example: {"color": "blue", "size": "256GB", "material": "aluminum"}

    # Keywords for matching
    keywords = Column(JSON, nullable=True)
    # Example: ["wireless", "bluetooth", "earbuds", "charging"]

    # Source reference (eBay or AliExpress listing ID)
    source_marketplace = Column(String(20), nullable=False)  # ebay, aliexpress
    source_listing_id = Column(Integer, nullable=False)

    def __repr__(self) -> str:
        return f"<NormalizedProduct(id={self.id}, title='{self.normalized_title[:50]}...')>"
