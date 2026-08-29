"""
Mock AliExpress adapter for MVP development and testing.

Returns realistic simulated product data based on keyword matching.
Used when real AliExpress API credentials are not available.

IMPORTANT:
- All data returned by this adapter is SIMULATED.
- Prices, ratings, and order counts are NOT real.
- Must never be used for actual purchasing decisions.
- UI must display clear DEMO MODE warning when this adapter is active.

Upgrade path:
- When real API credentials are available, switch ALIEXPRESS_MODE=production
  in .env and use OfficialAliExpressAdapter instead.
- The calling code does not change — only the adapter implementation.
"""
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

from config import settings
from utils.logger import get_logger
from utils.exceptions import AliExpressAPIError
from .base_adapter import BaseAliExpressAdapter
from .models import (
    AliExpressPrice,
    AliExpressProduct,
    AliExpressShipping,
    AliExpressStore,
)

logger = get_logger(__name__)

# Path to mock data file
MOCK_DATA_PATH = Path(__file__).parent.parent.parent / "tests" / "mocks" / "aliexpress_products.json"


class MockAliExpressAdapter(BaseAliExpressAdapter):
    """
    Mock AliExpress adapter using pre-defined product data.

    Simulates AliExpress product search using keyword matching
    against a curated set of realistic mock products.

    Search algorithm:
    1. Tokenize query into keywords
    2. For each mock product, calculate keyword overlap score
    3. Return top-N products sorted by relevance score
    4. Minimum score threshold prevents completely irrelevant results
    """

    # Minimum keyword overlap to include in results
    # 0 = any overlap, higher = stricter matching
    MIN_RELEVANCE_SCORE = 0

    def __init__(self, mock_data_path: Optional[Path] = None):
        """
        Initialize mock adapter.

        Args:
            mock_data_path: Path to mock data JSON file.
                            Defaults to tests/mocks/aliexpress_products.json
        """
        self._data_path = mock_data_path or MOCK_DATA_PATH
        self._products: Optional[List[dict]] = None
        logger.info(
            "MockAliExpressAdapter initialized — "
            "⚠️ DEMO MODE: All data is simulated"
        )

    def is_demo_mode(self) -> bool:
        """Always True for mock adapter."""
        return True

    def search_products(
        self,
        query: str,
        limit: int = 10,
    ) -> List[AliExpressProduct]:
        """
        Search mock products by keyword matching.

        Args:
            query: Search keywords
            limit: Maximum results to return

        Returns:
            List of matching AliExpressProduct objects.
            All products have source="mock".
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to mock adapter")
            return []

        limit = max(1, min(limit, 50))  # Clamp between 1 and 50

        logger.info(
            f"Mock AliExpress search: '{query}' (limit={limit})"
        )

        # Load mock data
        all_products = self._load_mock_data()

        if not all_products:
            logger.warning("No mock product data available")
            return []

        # Score each product by keyword relevance
        query_keywords = self._tokenize(query)
        scored = []

        for product_data in all_products:
            score = self._calculate_relevance(
                query_keywords,
                product_data,
            )
            if score > self.MIN_RELEVANCE_SCORE:
                scored.append((score, product_data))

        # Sort by relevance descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # If nothing matches at all, return diverse sample
        if not scored:
            logger.info(
                f"No keyword matches for '{query}' — "
                "returning diverse sample"
            )
            sample = all_products[:limit]
            return [self._build_product(p) for p in sample]

        # Convert top results to AliExpressProduct objects
        results = []
        for _, product_data in scored[:limit]:
            try:
                product = self._build_product(product_data)
                results.append(product)
            except Exception as e:
                logger.warning(
                    f"Failed to build product {product_data.get('product_id')}: {e}"
                )
                continue

        logger.info(
            f"Mock search returned {len(results)} products for '{query}'"
        )

        return results

    def get_product_details(
        self,
        product_id: str,
    ) -> Optional[AliExpressProduct]:
        """
        Get mock product by ID.

        Args:
            product_id: Product ID to look up

        Returns:
            AliExpressProduct if found, None otherwise
        """
        if not product_id:
            return None

        all_products = self._load_mock_data()

        for product_data in all_products:
            if product_data.get("product_id") == product_id:
                try:
                    return self._build_product(product_data)
                except Exception as e:
                    logger.error(
                        f"Failed to build product {product_id}: {e}"
                    )
                    return None

        logger.info(f"Mock product not found: {product_id}")
        return None

    def _load_mock_data(self) -> List[dict]:
        """
        Load mock product data from JSON file.

        Caches after first load.

        Returns:
            List of raw product dicts
        """
        if self._products is not None:
            return self._products

        if not self._data_path.exists():
            logger.error(
                f"Mock data file not found: {self._data_path}"
            )
            self._products = []
            return self._products

        try:
            with open(self._data_path, encoding="utf-8") as f:
                data = json.load(f)

            self._products = data.get("products", [])
            logger.info(
                f"Loaded {len(self._products)} mock AliExpress products"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse mock data JSON: {e}")
            self._products = []

        except OSError as e:
            logger.error(f"Failed to read mock data file: {e}")
            self._products = []

        return self._products

    def _tokenize(self, text: str) -> set:
        """
        Tokenize text into lowercase word set for matching.

        Args:
            text: Text to tokenize

        Returns:
            Set of lowercase word tokens (min 3 chars, stopwords removed)
        """
        # Common English stopwords to exclude from matching
        _STOPWORDS = {"the", "and", "for", "are", "but", "not", "you",
                    "all", "can", "her", "was", "one", "our", "out",
                    "day", "get", "has", "him", "his", "how", "its",
                    "may", "new", "now", "old", "see", "two", "way",
                    "who", "boy", "did", "its", "let", "put", "say",
                    "she", "too", "use", "an", "in", "on", "at", "to"}

        tokens = re.findall(r"[a-z0-9]+", text.lower())
        return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS}
    def _calculate_relevance(
        self,
        query_keywords: set,
        product_data: dict,
    ) -> float:
        """
        Calculate relevance score for a product against query keywords.

        Score = weighted overlap between query keywords and product signals.

        Weights:
        - Title keyword match: 2.0 per keyword
        - Product keyword list match: 1.5 per keyword
        - Category match: 3.0 (bonus if category word in query)
        - Attribute match: 1.0 per attribute value match

        Args:
            query_keywords: Set of tokenized query words
            product_data: Raw product dict from mock data

        Returns:
            Relevance score (higher = more relevant)
        """
        score = 0.0

        if not query_keywords:
            return 0.0

        # Title matching (highest weight)
        title_tokens = self._tokenize(
            product_data.get("title", "")
        )
        title_overlap = query_keywords & title_tokens
        score += len(title_overlap) * 2.0

        # Product keywords matching
        product_keywords = set(
            product_data.get("keywords", [])
        )
        keyword_overlap = query_keywords & product_keywords
        score += len(keyword_overlap) * 1.5

        # Category bonus
        category = product_data.get("category", "")
        if category and category in " ".join(query_keywords):
            score += 3.0

        # Attribute value matching
        attributes = product_data.get("attributes", {})
        for attr_value in attributes.values():
            attr_tokens = self._tokenize(str(attr_value))
            attr_overlap = query_keywords & attr_tokens
            score += len(attr_overlap) * 1.0

        return score

    def _build_product(self, data: dict) -> AliExpressProduct:
        """
        Convert raw mock data dict to AliExpressProduct.

        Args:
            data: Raw product dict from mock JSON

        Returns:
            AliExpressProduct with source="mock"

        Raises:
            ValueError: If required fields are missing
        """
        # Validate required fields
        product_id = data.get("product_id")
        title = data.get("title")
        price_value = data.get("price_value")
        product_url = data.get("product_url")

        if not all([product_id, title, price_value, product_url]):
            missing = [
                k for k, v in {
                    "product_id": product_id,
                    "title": title,
                    "price_value": price_value,
                    "product_url": product_url,
                }.items() if not v
            ]
            raise ValueError(
                f"Mock product missing required fields: {missing}"
            )

        # Build price
        original = data.get("original_price_value")
        price = AliExpressPrice(
            value=Decimal(str(price_value)),
            currency=data.get("price_currency", "USD"),
            original_value=(
                Decimal(str(original)) if original else None
            ),
        )

        # Build store
        store_name = data.get("store_name")
        store = None
        if store_name:
            store = AliExpressStore(
                name=store_name,
                store_id=data.get("store_id"),
                url=(
                    f"https://www.aliexpress.com/store/"
                    f"{data.get('store_id', '')}"
                    if data.get("store_id")
                    else None
                ),
            )

        # Build shipping
        shipping = []
        cost_str = data.get("shipping_cost", "0.00")
        try:
            shipping_cost = Decimal(str(cost_str))
        except Exception:
            shipping_cost = Decimal("0.00")

        shipping.append(
            AliExpressShipping(
                method=data.get(
                    "shipping_method",
                    "AliExpress Standard Shipping",
                ),
                cost=shipping_cost,
                currency=data.get("price_currency", "USD"),
                estimated_days_min=data.get("estimated_days_min"),
                estimated_days_max=data.get("estimated_days_max"),
            )
        )

        return AliExpressProduct(
            product_id=str(product_id),
            title=str(title),
            price=price,
            product_url=str(product_url),
            source="mock",
            image_url=data.get("image_url"),
            store=store,
            rating_score=data.get("rating_score"),
            review_count=data.get("review_count"),
            orders_count=data.get("orders_count"),
            attributes=data.get("attributes", {}),
            shipping_options=shipping,
        )