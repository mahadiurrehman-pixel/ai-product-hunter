"""
Product deduplication for search results.

Groups eBay listings that represent the same product from
different sellers. Keeps the best representative for each group.

Design:
- Uses normalized brand + product type + key attributes as identity
- Does NOT merge different variants (128GB vs 256GB stay separate)
- Preserves seller count and price range per group
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from services.scoring.normalizer import ProductNormalizer
from utils.logger import get_logger

logger = get_logger(__name__)

_normalizer = ProductNormalizer()


@dataclass
class ProductGroup:
    """
    A group of listings representing the same product.

    The 'representative' is the highest-ranked listing.
    """

    product_key: str  # identity string used for grouping
    representative: dict  # best listing in the group
    all_listings: List[dict] = field(default_factory=list)
    seller_count: int = 0
    price_min: Optional[Decimal] = None
    price_max: Optional[Decimal] = None
    total_sold: int = 0
    ranking_score: float = 0.0  # from ranker

    def to_dict(self) -> dict:
        return {
            "product_key": self.product_key,
            "representative": self.representative,
            "listing_count": len(self.all_listings),
            "seller_count": self.seller_count,
            "price_range": {
                "min": float(self.price_min) if self.price_min else None,
                "max": float(self.price_max) if self.price_max else None,
            },
            "total_sold": self.total_sold,
        }


class ProductDeduplicator:
    """
    Groups listings by product identity.

    Product identity = brand + product_type + key_differentiating_attributes.

    Key differentiating attributes include:
    - storage (128GB vs 256GB = different variants)
    - color (black vs white = different variants, may or may not group)
    - model (iPhone 15 vs iPhone 14 = different products)

    Same product from different sellers → grouped.
    Same product in different storage sizes → separate groups.
    """

    # Attributes that differentiate variants (NOT grouped together)
    VARIANT_ATTRIBUTES = {"storage", "memory", "size"}

    # Attributes that are cosmetic (grouped together by default)
    COSMETIC_ATTRIBUTES = {"color"}

    def deduplicate(
        self,
        listings: List[dict],
        group_colors: bool = True,
    ) -> List[ProductGroup]:
        """
        Group listings by product identity.

        Args:
            listings: List of parsed eBay listing dicts
            group_colors: If True, different colors of same product
                          are grouped together. If False, each color
                          is a separate group.

        Returns:
            List of ProductGroup, sorted by best ranking score descending.
        """
        if not listings:
            return []

        groups: Dict[str, ProductGroup] = {}

        for listing in listings:
            key = self._generate_product_key(listing, group_colors)

            if key not in groups:
                groups[key] = ProductGroup(
                    product_key=key,
                    representative=listing,
                )

            group = groups[key]
            group.all_listings.append(listing)
            self._update_group_stats(group, listing)

        # Sort groups by their representative's ranking potential
        result = sorted(
            groups.values(),
            key=lambda g: g.ranking_score,
            reverse=True,
        )

        logger.info(
            f"Deduplicated {len(listings)} listings into "
            f"{len(result)} product groups"
        )

        return result

    def _generate_product_key(
        self,
        listing: dict,
        group_colors: bool = True,
    ) -> str:
        """
        Generate a product identity key.

        Format: "{brand}|{product_type}|{variant_attrs}"

        Examples:
        - "apple|earbuds|"  (generic earbuds from Apple)
        - "apple|earbuds|storage:256gb"  (specific variant)
        - "unknown|earbuds|"  (no brand detected)
        """
        title = listing.get("title", "")
        normalized = _normalizer.normalize(title)

        brand = (normalized.brand or "unknown").lower()

        # Determine product type from keywords
        product_type = self._infer_product_type(normalized.keywords)

        # Build variant key from differentiating attributes
        variant_parts = []
        for attr in sorted(self.VARIANT_ATTRIBUTES):
            val = normalized.attributes.get(attr)
            if val:
                variant_parts.append(f"{attr}:{val.lower()}")

        if not group_colors:
            color = normalized.attributes.get("color")
            if color:
                variant_parts.append(f"color:{color.lower()}")

        variant_key = "|".join(variant_parts)

        return f"{brand}|{product_type}|{variant_key}"

    def _infer_product_type(self, keywords: List[str]) -> str:
        """
        Infer product type from keywords.

        Simple heuristic: use the first meaningful keyword that
        appears in a known product type vocabulary.
        """
        # Common product type indicators
        type_words = {
            "earbuds", "earphones", "headphones", "speaker",
            "charger", "cable", "case", "cover",
            "mouse", "keyboard", "monitor", "laptop",
            "phone", "tablet", "watch", "camera",
            "drone", "controller", "adapter", "hub",
        }

        for kw in keywords:
            if kw in type_words:
                return kw

        # Fallback: use first two keywords as identity
        if len(keywords) >= 2:
            return f"{keywords[0]}_{keywords[1]}"
        elif keywords:
            return keywords[0]
        return "unknown"

    def _update_group_stats(
        self,
        group: ProductGroup,
        listing: dict,
    ) -> None:
        """Update group statistics with new listing."""
        # Seller count
        sellers = set()
        for l in group.all_listings:
            seller = l.get("seller_username")
            if seller:
                sellers.add(seller)
        group.seller_count = len(sellers)

        # Price range
        price = listing.get("price_value")
        if price is not None:
            try:
                price_dec = Decimal(str(price))
                if group.price_min is None or price_dec < group.price_min:
                    group.price_min = price_dec
                if group.price_max is None or price_dec > group.price_max:
                    group.price_max = price_dec
            except Exception:
                pass

        # Total sold
        sold = listing.get("estimated_sold_quantity")
        if sold and isinstance(sold, (int, float)) and sold > 0:
            group.total_sold += int(sold)

        # Keep best representative (highest sold, then lowest price)
        current_best = group.representative
        best_sold = current_best.get("estimated_sold_quantity") or 0
        new_sold = listing.get("estimated_sold_quantity") or 0

        if new_sold > best_sold:
            group.representative = listing
        elif new_sold == best_sold:
            best_price = float(current_best.get("price_value", 999999))
            new_price = float(listing.get("price_value", 999999))
            if new_price < best_price:
                group.representative = listing