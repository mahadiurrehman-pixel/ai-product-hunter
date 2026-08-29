"""
Query-to-listing relevance scoring.

Calculates how relevant an eBay listing is to the user's search intent.
Uses weighted matching across product type, brand, model, and keywords.

This is the FIRST filter in the ranking pipeline — listings with low
relevance should be deprioritized before market/demand analysis.
"""
import re
from typing import Optional

from services.scoring.normalizer import ProductNormalizer
from utils.logger import get_logger
from .query_parser import SearchIntent

logger = get_logger(__name__)

_normalizer = ProductNormalizer()


class RelevanceScorer:
    """
    Scores how relevant an eBay listing is to a SearchIntent.

    Weighted components:
    - Product type match: 30 points
    - Brand match: 20 points
    - Model match: 25 points
    - Keyword overlap: up to 25 points

    Total possible: 100
    """

    WEIGHT_PRODUCT_TYPE = 30
    WEIGHT_BRAND = 20
    WEIGHT_MODEL = 25
    WEIGHT_KEYWORDS = 25

    DEFAULT_MIN_RELEVANCE = 25

    def score(
        self,
        intent: SearchIntent,
        listing: dict,
    ) -> float:
        """
        Calculate relevance score for a listing against search intent.

        Args:
            intent: Parsed SearchIntent from QueryParser
            listing: Parsed eBay listing dict

        Returns:
            Relevance score 0-100
        """
        if not intent or not intent.raw_query or not intent.raw_query.strip():
            return 0.0

        if not listing:
            return 0.0

        title = listing.get("title", "")
        if not title:
            return 0.0

        title_lower = title.lower()
        normalized = _normalizer.normalize(title)

        total = 0.0

        # Product type match
        total += self._score_product_type(intent, title_lower)

        # Brand match
        total += self._score_brand(intent, title_lower, normalized.brand)

        # Model match
        total += self._score_model(intent, title_lower)

        # Keyword overlap
        total += self._score_keywords(intent, normalized.keywords)

        return min(100.0, round(total, 1))

    def _score_product_type(
        self,
        intent: SearchIntent,
        title_lower: str,
    ) -> float:
        """Score product type match."""
        if not intent.product_type:
            return self.WEIGHT_PRODUCT_TYPE * 0.5

        from .query_parser import QueryParser
        parser = QueryParser()
        pt_data = parser._product_types.get(intent.product_type, {})
        aliases = pt_data.get("aliases", [intent.product_type])

        for alias in aliases:
            pattern = r"(?<!\w)" + re.escape(alias.lower()) + r"(?!\w)"
            if re.search(pattern, title_lower):
                return self.WEIGHT_PRODUCT_TYPE

        intent_kw = set(intent.keywords)
        title_words = set(title_lower.split())
        if intent_kw & title_words:
            return self.WEIGHT_PRODUCT_TYPE * 0.4

        return 0.0

    def _score_brand(
        self,
        intent: SearchIntent,
        title_lower: str,
        listing_brand: Optional[str],
    ) -> float:
        """Score brand match."""
        if not intent.brand:
            return self.WEIGHT_BRAND * 0.5

        intent_brand = intent.brand.lower()
        listing_brand_lower = (listing_brand or "").lower()

        if intent_brand == listing_brand_lower:
            return self.WEIGHT_BRAND

        if intent_brand in title_lower:
            return self.WEIGHT_BRAND * 0.9

        if listing_brand_lower and listing_brand_lower != intent_brand:
            return 0.0

        return self.WEIGHT_BRAND * 0.3

    def _score_model(
        self,
        intent: SearchIntent,
        title_lower: str,
    ) -> float:
        """Score model match."""
        if not intent.model:
            return self.WEIGHT_MODEL * 0.5

        model_lower = intent.model.lower()

        if model_lower in title_lower:
            return self.WEIGHT_MODEL

        model_words = model_lower.split()
        title_words = title_lower.split()
        match_count = sum(1 for w in model_words if w in title_words)

        if match_count >= len(model_words) * 0.7:
            return self.WEIGHT_MODEL * 0.8

        if match_count > 0:
            return self.WEIGHT_MODEL * 0.3

        return 0.0

    def _score_keywords(
        self,
        intent: SearchIntent,
        listing_keywords: list,
    ) -> float:
        """Score keyword overlap with diminishing returns."""
        if not intent.keywords or not listing_keywords:
            return 0.0

        intent_set = set(k.lower() for k in intent.keywords)
        listing_set = set(k.lower() for k in listing_keywords)

        overlap = intent_set & listing_set
        if not overlap:
            return 0.0

        ratio = len(overlap) / len(intent_set)
        return self.WEIGHT_KEYWORDS * min(1.0, ratio)