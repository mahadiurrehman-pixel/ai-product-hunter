"""
Match Repository — persists ProductMatchResult to product_matches table.

Follows existing repository patterns (EbayListingRepository).
Uses the existing ProductMatch SQLAlchemy model.
"""
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.match import ProductMatch
from models.ebay import EbayListing
from models.aliexpress import AliExpressListing
from utils.logger import get_logger
from .matcher import ProductMatchResult

logger = get_logger(__name__)


class MatchRepository:
    """Repository for product match persistence."""

    @staticmethod
    def save_match(
        db: Session, result: ProductMatchResult
    ) -> Optional[ProductMatch]:
        """
        Persist a ProductMatchResult to the product_matches table.

        Resolves eBay and AliExpress listing FKs from the database.
        Returns None if either listing is not found in the database.

        Args:
            db: Database session
            result: ProductMatchResult from ProductMatcher

        Returns:
            ProductMatch ORM instance, or None if FKs not found
        """
        # Resolve eBay listing FK
        ebay_listing = (
            db.query(EbayListing)
            .filter(EbayListing.item_id == result.ebay_item_id)
            .first()
        )
        if not ebay_listing:
            logger.warning(
                f"eBay listing not found in DB: {result.ebay_item_id}"
            )
            return None

        # Resolve AliExpress listing FK
        ali_listing = (
            db.query(AliExpressListing)
            .filter(
                AliExpressListing.product_id == result.ali_product_id
            )
            .first()
        )
        if not ali_listing:
            logger.warning(
                f"AliExpress listing not found in DB: "
                f"{result.ali_product_id}"
            )
            return None

        # Check for existing match (upsert)
        existing = (
            db.query(ProductMatch)
            .filter(
                ProductMatch.ebay_listing_id == ebay_listing.id,
                ProductMatch.aliexpress_listing_id == ali_listing.id,
            )
            .first()
        )

        match_data = {
            "ebay_listing_id": ebay_listing.id,
            "aliexpress_listing_id": ali_listing.id,
            "match_score": Decimal(str(round(result.match_score, 4))),
            "confidence": Decimal(str(round(result.confidence, 4))),
            "text_similarity": Decimal(
                str(round(result.text_similarity, 4))
            ),
            "semantic_similarity": None,  # Not implemented in MVP
            "attribute_similarity": Decimal(
                str(round(result.attribute_similarity, 4))
            ),
            "matching_reasons": result.matching_reasons,
            "differing_attributes": result.differing_attributes,
            "match_type": result.match_type,
        }

        if existing:
            for key, value in match_data.items():
                if key != "id":
                    setattr(existing, key, value)
            match = existing
            logger.debug(
                f"Updated match: eBay {result.ebay_item_id} "
                f"↔ Ali {result.ali_product_id}"
            )
        else:
            match = ProductMatch(**match_data)
            db.add(match)
            logger.debug(
                f"Created match: eBay {result.ebay_item_id} "
                f"↔ Ali {result.ali_product_id} "
                f"(score={result.match_score})"
            )

        try:
            db.commit()
            db.refresh(match)
            return match
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Failed to save match: {e}")
            raise

    @staticmethod
    def save_matches_bulk(
        db: Session, results: List[ProductMatchResult]
    ) -> List[ProductMatch]:
        """Save multiple match results."""
        saved = []
        for result in results:
            try:
                match = MatchRepository.save_match(db, result)
                if match:
                    saved.append(match)
            except Exception as e:
                logger.warning(
                    f"Failed to save match "
                    f"{result.ebay_item_id} ↔ "
                    f"{result.ali_product_id}: {e}"
                )
        return saved

    @staticmethod
    def get_matches_for_listing(
        db: Session,
        ebay_item_id: str,
        min_score: float = 0.0,
    ) -> List[ProductMatch]:
        """
        Get all matches for an eBay listing.

        Args:
            db: Database session
            ebay_item_id: eBay item ID string
            min_score: Minimum match score filter

        Returns:
            List of ProductMatch sorted by score descending
        """
        ebay_listing = (
            db.query(EbayListing)
            .filter(EbayListing.item_id == ebay_item_id)
            .first()
        )
        if not ebay_listing:
            return []

        return (
            db.query(ProductMatch)
            .filter(
                ProductMatch.ebay_listing_id == ebay_listing.id,
                ProductMatch.match_score >= Decimal(str(min_score)),
            )
            .order_by(ProductMatch.match_score.desc())
            .all()
        )

    @staticmethod
    def get_best_match(
        db: Session, ebay_item_id: str
    ) -> Optional[ProductMatch]:
        """Get the highest-scoring match for an eBay listing."""
        matches = MatchRepository.get_matches_for_listing(
            db, ebay_item_id, min_score=0.0
        )
        return matches[0] if matches else None