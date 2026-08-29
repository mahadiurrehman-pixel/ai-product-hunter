"""
Product match database models.
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    Numeric,
    DateTime,
    JSON,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class ProductMatch(Base, TimestampMixin):
    """
    Product match between eBay and AliExpress listings.
    """

    __tablename__ = "product_matches"

    # Foreign keys
    ebay_listing_id = Column(Integer, ForeignKey("ebay_listings.id"), nullable=False)
    aliexpress_listing_id = Column(
        Integer, ForeignKey("aliexpress_listings.id"), nullable=False
    )

    # Match scores
    match_score = Column(Numeric(5, 4), nullable=False)  # 0.0000 to 1.0000
    confidence = Column(Numeric(5, 4), nullable=False)

    # Score breakdown
    text_similarity = Column(Numeric(5, 4), nullable=True)
    semantic_similarity = Column(Numeric(5, 4), nullable=True)
    attribute_similarity = Column(Numeric(5, 4), nullable=True)

    # Matching reasons
    matching_reasons = Column(JSON, nullable=True)
    # Example: ["same brand", "same capacity", "high semantic similarity"]

    differing_attributes = Column(JSON, nullable=True)
    # Example: ["color: blue vs red", "material: plastic vs metal"]

    # Match metadata
    match_type = Column(
        String(20), nullable=False
    )  # exact, very_similar, similar, possible
    matched_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    ebay_listing = relationship("EbayListing", back_populates="matches")
    aliexpress_listing = relationship("AliExpressListing", back_populates="matches")
    opportunity_scores = relationship(
        "OpportunityScoreRecord", back_populates="product_match"
    )
    watchlist_items = relationship("WatchlistItem", back_populates="product_match")

    # Indexes
    __table_args__ = (
        Index("idx_match_ebay", "ebay_listing_id"),
        Index("idx_match_ali", "aliexpress_listing_id"),
        Index("idx_match_score", "match_score"),
        Index("idx_match_type", "match_type"),
    )

    def __repr__(self) -> str:
        return f"<ProductMatch(id={self.id}, score={self.match_score}, type='{self.match_type}')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "ebay_listing_id": self.ebay_listing_id,
            "aliexpress_listing_id": self.aliexpress_listing_id,
            "match_score": float(self.match_score),
            "confidence": float(self.confidence),
            "match_type": self.match_type,
            "similarity_breakdown": {
                "text": float(self.text_similarity) if self.text_similarity else None,
                "semantic": float(self.semantic_similarity)
                if self.semantic_similarity
                else None,
                "attributes": float(self.attribute_similarity)
                if self.attribute_similarity
                else None,
            },
            "matching_reasons": self.matching_reasons,
            "differing_attributes": self.differing_attributes,
            "matched_at": self.matched_at.isoformat() if self.matched_at else None,
        }
