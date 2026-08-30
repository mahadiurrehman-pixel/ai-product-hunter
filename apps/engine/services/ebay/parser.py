"""
eBay Browse API response parser.

Converts eBay API responses into internal data models.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from config import settings
from utils.logger import get_logger
from .exceptions import EbayInvalidResponseError

logger = get_logger(__name__)


class EbayParser:
    """
    Parser for eBay Browse API responses.

    Converts API JSON responses into structured data compatible
    with the EbayListing database model.
    """

    @staticmethod
    def parse_search_response(
        response_data: dict,
        marketplace: Optional[str] = None,
    ) -> dict:
        """
        Parse eBay item_summary/search response.

        Args:
            response_data: Raw API response JSON
            marketplace: eBay marketplace ID to inject into each parsed item

        Returns:
            Parsed response with metadata and items.
        """
        if not isinstance(response_data, dict):
            raise EbayInvalidResponseError(
                "Response must be a dictionary",
                details={"type": type(response_data).__name__},
            )

        total = response_data.get("total", 0)
        limit = response_data.get("limit", 0)
        offset = response_data.get("offset", 0)

        items_raw = response_data.get("itemSummaries", [])

        if not isinstance(items_raw, list):
            raise EbayInvalidResponseError(
                "itemSummaries must be a list", field="itemSummaries"
            )

        items = []
        for item_data in items_raw:
            try:
                parsed = EbayParser.parse_item_summary(
                    item_data, marketplace=marketplace
                )
                items.append(parsed)
            except Exception as e:
                logger.warning(f"Failed to parse item: {e}")
                continue

        logger.info(
            f"Parsed eBay search: {len(items)}/{total} items "
            f"(limit={limit}, offset={offset}, "
            f"marketplace={marketplace or 'unspecified'})"
        )

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": items,
            "items_count": len(items),
        }

    @staticmethod
    def parse_item_summary(
        item_data: dict,
        marketplace: Optional[str] = None,
    ) -> dict:
        """
        Parse individual item from search results.

        Safely extracts product title, pricing, main image URL,
        official eBay listing URL, seller metrics, and attributes.
        """
        if not isinstance(item_data, dict):
            raise EbayInvalidResponseError(
                "Item data must be a dictionary",
                details={"type": type(item_data).__name__},
            )

        item_id = item_data.get("itemId")
        if not item_id:
            raise EbayInvalidResponseError(
                "Item missing itemId", field="itemId"
            )

        title = item_data.get("title", "")
        if not title:
            logger.warning(f"Item {item_id} has no title")

        # Price parsing
        price_data = item_data.get("price") or {}
        price_value = price_data.get("value") if isinstance(price_data, dict) else None
        price_currency = (
            price_data.get("currency", "USD")
            if isinstance(price_data, dict)
            else "USD"
        )

        if price_value is None:
            logger.warning(f"Item {item_id} has no price")
            price_value = 0.0

        # Safe primary image extraction
        image_url = None
        image_data = item_data.get("image")
        if isinstance(image_data, dict):
            image_url = image_data.get("imageUrl")
        elif isinstance(image_data, str) and image_data.strip():
            image_url = image_data.strip()

        # Fallback to top-level image fields if present
        if not image_url:
            for key in ("imageUrl", "image_url"):
                val = item_data.get(key)
                if isinstance(val, str) and val.strip():
                    image_url = val.strip()
                    break

        # Safe additional images extraction
        additional_images_data = item_data.get("additionalImages")
        additional_images = None
        if isinstance(additional_images_data, list):
            extracted = [
                img.get("imageUrl")
                for img in additional_images_data
                if isinstance(img, dict) and img.get("imageUrl")
            ]
            if extracted:
                additional_images = extracted

        # Safe listing URL extraction
        item_web_url = None
        for url_key in ("itemWebUrl", "item_web_url", "itemUrl", "item_url"):
            val = item_data.get(url_key)
            if isinstance(val, str) and val.strip():
                item_web_url = val.strip()
                break

        # Category parsing
        categories = item_data.get("categories")
        category_id = None
        category_name = None
        if isinstance(categories, list) and len(categories) > 0 and isinstance(categories[0], dict):
            category_id = categories[0].get("categoryId")
            category_name = categories[0].get("categoryName")

        category_path = item_data.get("categoryPath")
        condition = item_data.get("condition")
        condition_description = item_data.get("conditionDescription")

        # Seller parsing
        seller_data = item_data.get("seller") or {}
        seller_username = None
        seller_feedback_percentage = None
        seller_feedback_score = None
        if isinstance(seller_data, dict):
            seller_username = seller_data.get("username")
            raw_feedback = seller_data.get("feedbackPercentage")
            if raw_feedback is not None:
                try:
                    seller_feedback_percentage = float(raw_feedback)
                except (ValueError, TypeError):
                    seller_feedback_percentage = None
            seller_feedback_score = seller_data.get("feedbackScore")

        buying_options = item_data.get("buyingOptions")
        shipping_options = item_data.get("shippingOptions")
        item_location = item_data.get("itemLocation")

        product_data = item_data.get("product") or {}
        product_brand = None
        product_mpn = None
        product_aspects = None
        if isinstance(product_data, dict):
            product_brand = product_data.get("brand")
            product_mpn = product_data.get("mpn")
            product_aspects = product_data.get("aspects")

        # Estimated availability
        estimated_availabilities = item_data.get("estimatedAvailabilities")
        estimated_available_quantity = None
        estimated_sold_quantity = None
        if (
            isinstance(estimated_availabilities, list)
            and len(estimated_availabilities) > 0
            and isinstance(estimated_availabilities[0], dict)
        ):
            avail = estimated_availabilities[0]
            estimated_available_quantity = avail.get("estimatedAvailableQuantity")
            estimated_sold_quantity = avail.get("estimatedSoldQuantity")

        fetched_at = datetime.utcnow()
        cache_expires_at = fetched_at + timedelta(
            hours=settings.cache_search_results_ttl_hours
        )

        result = {
            "item_id": item_id,
            "title": title,
            "description": item_data.get("description"),
            "price_value": Decimal(str(price_value)),
            "price_currency": price_currency,
            "image_url": image_url,
            "additional_images": additional_images,
            "item_web_url": item_web_url,
            "category_id": category_id,
            "category_name": category_name,
            "category_path": category_path,
            "condition": condition,
            "condition_description": condition_description,
            "seller_username": seller_username,
            "seller_feedback_percentage": seller_feedback_percentage,
            "seller_feedback_score": seller_feedback_score,
            "buying_options": buying_options if isinstance(buying_options, list) else None,
            "shipping_options": shipping_options if isinstance(shipping_options, list) else None,
            "item_location": item_location if isinstance(item_location, dict) else None,
            "product_brand": product_brand,
            "product_mpn": product_mpn,
            "product_aspects": product_aspects if isinstance(product_aspects, dict) else None,
            "estimated_available_quantity": estimated_available_quantity,
            "estimated_sold_quantity": estimated_sold_quantity,
            "raw_data": item_data,
            "fetched_at": fetched_at,
            "cache_expires_at": cache_expires_at,
        }

        if marketplace is not None:
            result["marketplace"] = marketplace

        return result

    @staticmethod
    def parse_item_details(
        item_data: dict,
        marketplace: Optional[str] = None,
    ) -> dict:
        """Parse detailed item response from item/{item_id} endpoint."""
        result = EbayParser.parse_item_summary(
            item_data, marketplace=marketplace
        )
        fetched_at = datetime.utcnow()
        result["fetched_at"] = fetched_at
        result["cache_expires_at"] = fetched_at + timedelta(
            hours=settings.cache_product_details_ttl_hours
        )
        return result