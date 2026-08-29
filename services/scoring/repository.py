"""
Opportunity Score Database Repository.

Handles persistence and querying of UnifiedOpportunityScore results
in the opportunity_scores table (OpportunityScoreRecord ORM model).
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.match import ProductMatch
from models.score import OpportunityScoreRecord
from services.scoring.unified_scorer import UnifiedOpportunityScore
from utils.logger import get_logger

logger = get_logger(__name__)


def _to_decimal_str(val: float, precision: int = 2) -> Decimal:
    """Safely round and convert float to Decimal."""
    return Decimal(str(round(float(val), precision)))


class OpportunityScoreRepository:
    """Repository for opportunity score persistence and querying."""

    @staticmethod
    def save_score(
        db: Session,
        score: UnifiedOpportunityScore,
        product_match_id: int,
    ) -> Optional[OpportunityScoreRecord]:
        """
        Persist or update an opportunity score for a specific product match.

        Performs an upsert based on product_match_id.

        Args:
            db: Database session
            score: UnifiedOpportunityScore output model
            product_match_id: Foreign key ID of the ProductMatch

        Returns:
            Saved OpportunityScoreRecord ORM instance, or None if ProductMatch not found.
        """
        # 1. Verify ProductMatch exists
        match_exists = (
            db.query(ProductMatch.id)
            .filter(ProductMatch.id == product_match_id)
            .first()
        )
        if not match_exists:
            logger.warning(
                f"ProductMatch ID {product_match_id} not found in database. Cannot persist score."
            )
            return None

        # 2. Check for existing score record (upsert)
        existing = (
            db.query(OpportunityScoreRecord)
            .filter(OpportunityScoreRecord.product_match_id == product_match_id)
            .first()
        )

        # 3. Map fields to DB schema
        confidence_numeric = (
            Decimal("0.9000")
            if score.confidence == "high"
            else Decimal("0.6500")
            if score.confidence == "medium"
            else Decimal("0.3500")
        )

        score_data = {
            "product_match_id": product_match_id,
            "overall_score": _to_decimal_str(score.final_score, 2),
            "confidence": confidence_numeric,
            "market_signals_score": _to_decimal_str(score.market_score, 2),
            "competition_signals_score": _to_decimal_str(score.competition_score, 2),
            "economics_signals_score": _to_decimal_str(score.economics_score, 2),
            "supplier_match_signals_score": _to_decimal_str(score.match_quality_score, 2),
            "market_signals_detail": score.market_details,
            "competition_signals_detail": score.competition_details,
            "economics_signals_detail": score.economics_details,
            "supplier_match_signals_detail": score.match_details,
            "recommendation": score.recommendation.value,
            "reasoning": score.reasoning,
            "weights_used": score.weights_used,
            "evidence": {
                "policy_penalty": score.policy_penalty,
                "policy_risk_level": score.policy_risk_level,
                "raw_weighted_score": score.raw_weighted_score,
                "confidence_bonus": score.confidence_bonus,
                "warnings": score.warnings,
                "assumptions": score.assumptions,
            },
            "calculated_at": datetime.utcnow(),
        }

        if existing:
            for key, value in score_data.items():
                setattr(existing, key, value)
            record = existing
            logger.debug(f"Updated opportunity score for match ID {product_match_id}")
        else:
            record = OpportunityScoreRecord(**score_data)
            db.add(record)
            logger.debug(f"Created opportunity score for match ID {product_match_id}")

        try:
            db.commit()
            db.refresh(record)
            return record
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Failed to persist opportunity score: {e}")
            raise

    @staticmethod
    def get_by_match_id(
        db: Session, product_match_id: int
    ) -> Optional[OpportunityScoreRecord]:
        """
        Get opportunity score by ProductMatch ID.

        Args:
            db: Database session
            product_match_id: Foreign key ID of the ProductMatch

        Returns:
            OpportunityScoreRecord instance if found, else None
        """
        return (
            db.query(OpportunityScoreRecord)
            .filter(OpportunityScoreRecord.product_match_id == product_match_id)
            .first()
        )

    @staticmethod
    def get_top_opportunities(
        db: Session,
        limit: int = 20,
        min_score: float = 50.0,
    ) -> List[OpportunityScoreRecord]:
        """
        Get highest-scoring opportunity records.

        Args:
            db: Database session
            limit: Maximum records to return
            min_score: Minimum overall opportunity score filter

        Returns:
            List of OpportunityScoreRecord sorted by overall_score descending
        """
        return (
            db.query(OpportunityScoreRecord)
            .filter(OpportunityScoreRecord.overall_score >= Decimal(str(min_score)))
            .order_by(OpportunityScoreRecord.overall_score.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_recent_scores(
        db: Session, limit: int = 50
    ) -> List[OpportunityScoreRecord]:
        """
        Get recently calculated opportunity score records.

        Args:
            db: Database session
            limit: Maximum records to return

        Returns:
            List of OpportunityScoreRecord sorted by calculated_at descending
        """
        return (
            db.query(OpportunityScoreRecord)
            .order_by(OpportunityScoreRecord.calculated_at.desc())
            .limit(limit)
            .all()
        )