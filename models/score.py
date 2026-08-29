"""
Opportunity score database models.
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
    Text,
    Index,
    String,
)
from sqlalchemy.orm import relationship

from .base import Base, TimestampMixin


class OpportunityScoreRecord(Base, TimestampMixin):
    """
    Opportunity score calculation record.
    """

    __tablename__ = "opportunity_scores"

    # Foreign key
    product_match_id = Column(Integer, ForeignKey("product_matches.id"), nullable=False)

    # Overall score
    overall_score = Column(Numeric(5, 2), nullable=False)  # 0.00 to 100.00
    confidence = Column(Numeric(5, 4), nullable=False)  # 0.0000 to 1.0000

    # Component scores
    market_signals_score = Column(Numeric(5, 2), nullable=False)
    competition_signals_score = Column(Numeric(5, 2), nullable=False)
    economics_signals_score = Column(Numeric(5, 2), nullable=False)
    supplier_match_signals_score = Column(Numeric(5, 2), nullable=False)

    # Detailed breakdowns (JSON)
    market_signals_detail = Column(JSON, nullable=True)
    competition_signals_detail = Column(JSON, nullable=True)
    economics_signals_detail = Column(JSON, nullable=True)
    supplier_match_signals_detail = Column(JSON, nullable=True)

    # Recommendation
    recommendation = Column(String(100), nullable=False)
    reasoning = Column(JSON, nullable=True)  # List of reasoning points

    # Configuration used
    weights_used = Column(JSON, nullable=False)

    # Evidence
    evidence = Column(JSON, nullable=True)

    # Calculation metadata
    calculated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    product_match = relationship("ProductMatch", back_populates="opportunity_scores")

    # Indexes
    __table_args__ = (
        Index("idx_score_overall", "overall_score"),
        Index("idx_score_match", "product_match_id"),
        Index("idx_score_calculated", "calculated_at"),
    )

    def __repr__(self) -> str:
        return f"<OpportunityScore(id={self.id}, score={self.overall_score}, recommendation='{self.recommendation}')>"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "product_match_id": self.product_match_id,
            "overall_score": float(self.overall_score),
            "confidence": float(self.confidence),
            "recommendation": self.recommendation,
            "component_scores": {
                "market_signals": float(self.market_signals_score),
                "competition_signals": float(self.competition_signals_score),
                "economics_signals": float(self.economics_signals_score),
                "supplier_match_signals": float(self.supplier_match_signals_score),
            },
            "reasoning": self.reasoning,
            "calculated_at": self.calculated_at.isoformat()
            if self.calculated_at
            else None,
        }
