"""
eBay listing database repository.

Handles persistence of eBay listings to database.
Uses composite (marketplace, item_id) key for upsert operations
so listings from different marketplaces don't overwrite each other.
"""
from typing import List, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from models.ebay import EbayListing
from utils.logger import get_logger

logger = get_logger(__name__)


class EbayListingRepository:
    """Repository for eBay listing database operations."""

    @staticmethod
    def save_listing(db: Session, listing_data: dict) -> EbayListing:
        """
        Save or update eBay listing in database.

        Upsert uses (marketplace, item_id) composite key.
        If marketplace is missing from listing_data, defaults to EBAY_US
        for backward compatibility with existing records.

        Args:
            db: Database session
            listing_data: Parsed listing data from parser

        Returns:
            Saved listing model
        """
        # Ensure marketplace is set (default EBAY_US for backward compat)
        marketplace = listing_data.get("marketplace", "EBAY_US")
        item_id = listing_data["item_id"]

        # Look up existing by (marketplace, item_id) composite
        existing = (
            db.query(EbayListing)
            .filter(
                EbayListing.marketplace == marketplace,
                EbayListing.item_id == item_id,
            )
            .first()
        )

        # Ensure listing_data has marketplace set for insert
        listing_data_to_save = dict(listing_data)
        listing_data_to_save["marketplace"] = marketplace

        if existing:
            for key, value in listing_data_to_save.items():
                if key != "id":
                    setattr(existing, key, value)

            existing.updated_at = datetime.utcnow()
            listing = existing
            logger.debug(
                f"Updated existing listing: "
                f"marketplace={marketplace}, item_id={item_id}"
            )
        else:
            listing = EbayListing(**listing_data_to_save)
            db.add(listing)
            logger.debug(
                f"Created new listing: "
                f"marketplace={marketplace}, item_id={item_id}"
            )

        try:
            db.commit()
            db.refresh(listing)
            return listing
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Failed to save listing: {e}")
            raise

    @staticmethod
    def save_listings_bulk(
        db: Session, listings_data: List[dict]
    ) -> List[EbayListing]:
        """
        Save multiple listings in bulk.
        """
        saved_listings = []

        for listing_data in listings_data:
            try:
                listing = EbayListingRepository.save_listing(
                    db, listing_data
                )
                saved_listings.append(listing)
            except Exception as e:
                logger.warning(
                    f"Failed to save listing "
                    f"{listing_data.get('item_id')}: {e}"
                )
                continue

        logger.info(
            f"Saved {len(saved_listings)}/{len(listings_data)} listings"
        )

        return saved_listings

    @staticmethod
    def get_by_item_id(
        db: Session,
        item_id: str,
        marketplace: Optional[str] = None,
    ) -> Optional[EbayListing]:
        """
        Get listing by eBay item ID.

        Args:
            db: Database session
            item_id: eBay item ID
            marketplace: Optional marketplace filter. If provided,
                         looks up the specific (marketplace, item_id) pair.
                         If None, returns the first matching item_id
                         across any marketplace (backward compatibility).

        Returns:
            Listing if found, None otherwise
        """
        query = db.query(EbayListing).filter(
            EbayListing.item_id == item_id
        )

        if marketplace is not None:
            query = query.filter(EbayListing.marketplace == marketplace)

        return query.first()

    @staticmethod
    def get_by_marketplace_and_item(
        db: Session,
        marketplace: str,
        item_id: str,
    ) -> Optional[EbayListing]:
        """
        Get listing by explicit (marketplace, item_id) composite key.

        Preferred method when marketplace is known.

        Args:
            db: Database session
            marketplace: eBay marketplace ID (e.g., "EBAY_US")
            item_id: eBay item ID

        Returns:
            Listing if found, None otherwise
        """
        return (
            db.query(EbayListing)
            .filter(
                EbayListing.marketplace == marketplace,
                EbayListing.item_id == item_id,
            )
            .first()
        )

    @staticmethod
    def get_recent_listings(
        db: Session,
        limit: int = 50,
        hours: int = 24,
        marketplace: Optional[str] = None,
    ) -> List[EbayListing]:
        """
        Get recently fetched listings.

        Args:
            db: Database session
            limit: Max listings to return
            hours: How many hours back to search
            marketplace: Optional marketplace filter

        Returns:
            List of recent listings
        """
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        query = db.query(EbayListing).filter(
            EbayListing.fetched_at >= cutoff
        )

        if marketplace is not None:
            query = query.filter(EbayListing.marketplace == marketplace)

        return (
            query.order_by(EbayListing.fetched_at.desc())
            .limit(limit)
            .all()
        )