"""
Watchlist database models.
"""
from sqlalchemy import Column, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class WatchlistItem(Base, TimestampMixin):
    """
    User watchlist item.

    Stores products user wants to monitor.
    """

    __tablename__ = "watchlist_items"

    # Foreign key to product match
    product_match_id = Column(Integer, ForeignKey("product_matches.id"), nullable=False)

    # User notes
    notes = Column(Text, nullable=True)

    # Future: user_id for multi-tenant
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationship
    product_match = relationship("ProductMatch", back_populates="watchlist_items")

    def __repr__(self) -> str:
        return f"<WatchlistItem(id={self.id}, match_id={self.product_match_id})>"
