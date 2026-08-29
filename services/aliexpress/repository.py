"""
AliExpress listing database repository.

Handles persistence of AliExpress products to the database.
Works with both mock and real API data — source field distinguishes them.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.aliexpress import AliExpressListing
from utils.logger import get_logger
from .models import AliExpressProduct

logger = get_logger(__name__)


class AliExpressRepository:
    """Repository for AliExpress listing database operations."""

    @staticmethod
    def save_product(
        db: Session,
        product: AliExpressProduct,
    ) -> AliExpressListing:
        """
        Save or update an AliExpress product in the database.

        Uses upsert logic — if product_id already exists, updates it.

        Args:
            db: Database session
            product: AliExpressProduct to persist

        Returns:
            Saved AliExpressListing model instance
        """
        existing = (
            db.query(AliExpressListing)
            .filter(
                AliExpressListing.product_id == product.product_id
            )
            .first()
        )

        db_data = product.to_db_dict()

        if existing:
            for key, value in db_data.items():
                if key != "id":
                    setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            listing = existing
            logger.debug(
                f"Updated AliExpress listing: {product.product_id}"
            )
        else:
            listing = AliExpressListing(**db_data)
            db.add(listing)
            logger.debug(
                f"Created AliExpress listing: {product.product_id}"
            )

        try:
            db.commit()
            db.refresh(listing)
            return listing
        except IntegrityError as e:
            db.rollback()
            logger.error(
                f"Failed to save AliExpress listing "
                f"{product.product_id}: {e}"
            )
            raise

    @staticmethod
    def save_products_bulk(
        db: Session,
        products: List[AliExpressProduct],
    ) -> List[AliExpressListing]:
        """
        Save multiple products in bulk.

        Args:
            db: Database session
            products: List of AliExpressProduct objects

        Returns:
            List of successfully saved listings
        """
        saved = []

        for product in products:
            try:
                listing = AliExpressRepository.save_product(
                    db, product
                )
                saved.append(listing)
            except Exception as e:
                logger.warning(
                    f"Failed to save product "
                    f"{product.product_id}: {e}"
                )
                continue

        logger.info(
            f"Saved {len(saved)}/{len(products)} AliExpress products"
        )
        return saved

    @staticmethod
    def get_by_product_id(
        db: Session,
        product_id: str,
    ) -> Optional[AliExpressListing]:
        """
        Get listing by AliExpress product ID.

        Args:
            db: Database session
            product_id: AliExpress product ID

        Returns:
            AliExpressListing if found, None otherwise
        """
        return (
            db.query(AliExpressListing)
            .filter(AliExpressListing.product_id == product_id)
            .first()
        )

    @staticmethod
    def get_by_source(
        db: Session,
        source: str,
        limit: int = 50,
    ) -> List[AliExpressListing]:
        """
        Get listings by data source.

        Args:
            db: Database session
            source: "mock", "api", or "affiliate"
            limit: Maximum results

        Returns:
            List of AliExpressListing objects
        """
        return (
            db.query(AliExpressListing)
            .filter(AliExpressListing.source == source)
            .limit(limit)
            .all()
        )