"""
Product text normalization and attribute extraction.

Provides deterministic, rule-based text cleaning and attribute extraction
for product titles. No ML/LLM/embeddings - keeps it simple for MVP.
"""
import re
from typing import Dict, List, Optional, Set
from dataclasses import dataclass

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class NormalizedProduct:
    """
    Normalized product data extracted from title.

    All fields are extracted using deterministic rules, not ML.
    """

    original_title: str
    normalized_title: str
    brand: Optional[str]
    keywords: List[str]
    attributes: Dict[str, str]
    category_hints: List[str]


class ProductNormalizer:
    """
    Normalizes product titles using rule-based pattern matching.

    Deterministic approach suitable for MVP:
    - Text cleaning
    - Brand extraction from known list
    - Attribute extraction via regex
    - Keyword extraction
    - Category detection
    """

    KNOWN_BRANDS = {
        "apple",
        "samsung",
        "sony",
        "lg",
        "dell",
        "hp",
        "lenovo",
        "asus",
        "acer",
        "microsoft",
        "google",
        "amazon",
        "bose",
        "jbl",
        "beats",
        "anker",
        "xiaomi",
        "huawei",
        "oneplus",
        "motorola",
        "nokia",
        "panasonic",
        "philips",
        "logitech",
        "razer",
        "corsair",
        "kingston",
        "sandisk",
        "seagate",
        "western digital",
        "wd",
        "intel",
        "amd",
        "nvidia",
        "canon",
        "nikon",
        "gopro",
    }

    COLOR_PATTERN = re.compile(
        r"\b(black|white|silver|gold|rose gold|blue|red|green|"
        r"yellow|pink|purple|gray|grey|bronze|space gray|midnight)\b",
        re.IGNORECASE,
    )

    # Memory/RAM pattern — must be matched BEFORE storage
    # Matches: "16GB RAM", "32GB Memory", "8 GB RAM"
    MEMORY_PATTERN = re.compile(
        r"\b(\d+)\s*gb\s*(ram|memory)\b", re.IGNORECASE
    )

    # Storage pattern — context-aware
    # Matches GB/TB/MB values that are NOT followed by RAM/Memory keywords
    # Matches: "256GB", "512GB SSD", "1TB", "256 GB"
    # Does NOT match: "16GB RAM", "32GB Memory"
    STORAGE_PATTERN = re.compile(
        r"\b(\d+)\s*(gb|tb|mb)\b(?!\s*(?:ram|memory))",
        re.IGNORECASE,
    )

    # Size/dimension pattern — handles both numeric words and " symbol
    # Matches: '55"', "13 inch", "15.6 inches", "6.7 inch", "10cm"
    # Fix: don't use \b before " since " is not a word character
    SIZE_PATTERN = re.compile(
        r'(\d+\.?\d*)\s*(inch(?:es)?|cm|mm)|(\d+\.?\d*)"',
        re.IGNORECASE,
    )

    STOPWORDS = {
        "new",
        "brand",
        "sealed",
        "free",
        "shipping",
        "fast",
        "genuine",
        "original",
        "authentic",
        "official",
        "oem",
        "factory",
        "unlocked",
        "warranty",
        "refurbished",
        "used",
        "pre",
        "owned",
        "preowned",
        "like",
        "condition",
        "excellent",
        "good",
        "fair",
        "perfect",
        "great",
        "amazing",
        "best",
        "top",
        "quality",
        "hot",
        "sale",
        "deal",
        "bargain",
        "lot",
        "bundle",
        "set",
        "pack",
    }

    def normalize(
        self, title: str, description: Optional[str] = None
    ) -> NormalizedProduct:
        """
        Normalize product title and extract attributes.

        Args:
            title: Product title from eBay
            description: Optional description (not used in MVP)

        Returns:
            NormalizedProduct with extracted information
        """
        if not title or not title.strip():
            logger.warning("Empty title provided for normalization")
            return NormalizedProduct(
                original_title="",
                normalized_title="",
                brand=None,
                keywords=[],
                attributes={},
                category_hints=[],
            )

        normalized = self._clean_text(title)
        brand = self._extract_brand(title)
        attributes = self._extract_attributes(title)
        keywords = self._extract_keywords(normalized)
        category_hints = self._extract_category_hints(title)

        return NormalizedProduct(
            original_title=title,
            normalized_title=normalized,
            brand=brand,
            keywords=keywords,
            attributes=attributes,
            category_hints=category_hints,
        )

    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text.

        Steps:
        1. Lowercase
        2. Remove special characters (keep alphanumeric + spaces)
        3. Remove extra whitespace
        4. Remove stopwords

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = " ".join(text.split())
        words = text.split()
        words = [w for w in words if w not in self.STOPWORDS]
        return " ".join(words)

    def _extract_brand(self, text: str) -> Optional[str]:
        """
        Extract brand name from title.

        Uses word boundary matching against known brand list.

        Args:
            text: Product title

        Returns:
            Brand name (title case) or None
        """
        text_lower = text.lower()

        for brand in self.KNOWN_BRANDS:
            pattern = r"\b" + re.escape(brand) + r"\b"
            if re.search(pattern, text_lower):
                return brand.title()

        return None

    def _extract_attributes(self, text: str) -> Dict[str, str]:
        """
        Extract product attributes using regex patterns.

        Extraction order matters:
        1. Memory/RAM (extracted first to prevent storage pattern
           from capturing RAM values)
        2. Storage (excludes values already identified as RAM)
        3. Color
        4. Size/dimensions

        Args:
            text: Product title

        Returns:
            Dict of attribute_name: value
        """
        attributes = {}

        # Step 1: Extract memory/RAM FIRST
        # This prevents "16GB RAM" from being captured as storage
        memory_match = self.MEMORY_PATTERN.search(text)
        if memory_match:
            attributes["memory"] = f"{memory_match.group(1)}GB"

        # Step 2: Extract storage
        # STORAGE_PATTERN uses negative lookahead to exclude RAM/memory
        # so "16GB RAM" will not match, but "512GB SSD" or "256GB" will
        storage_match = self.STORAGE_PATTERN.search(text)
        if storage_match:
            value = storage_match.group(1)
            unit = storage_match.group(2).upper()
            candidate = f"{value}{unit}"
            # Additional guard: skip if this value was already
            # captured as memory
            if "memory" not in attributes or attributes["memory"] != candidate:
                attributes["storage"] = candidate

        # Step 3: Color
        color_match = self.COLOR_PATTERN.search(text)
        if color_match:
            attributes["color"] = color_match.group(1).lower()

        # Step 4: Size/dimensions
        # SIZE_PATTERN handles both "55\"" and "13 inch" forms
        size_match = self.SIZE_PATTERN.search(text)
        if size_match:
            if size_match.group(3) is not None:
                # Matched the (\d+\.?\d*)" form (group 3)
                value = size_match.group(3)
                unit = "inch"
            else:
                # Matched the (\d+\.?\d*)\s*(inch|cm|mm) form
                value = size_match.group(1)
                unit = size_match.group(2).lower()
                if unit in ["inches"]:
                    unit = "inch"
            attributes["size"] = f"{value}{unit}"

        return attributes

    def _extract_keywords(self, normalized_text: str) -> List[str]:
        """
        Extract important keywords from normalized text.

        Filters:
        - At least 3 characters
        - Not pure numbers
        - Deduplicated

        Args:
            normalized_text: Already cleaned text

        Returns:
            List of unique keywords
        """
        words = normalized_text.split()

        keywords = [
            word for word in words if len(word) >= 3 and not word.isdigit()
        ]

        seen: Set[str] = set()
        unique_keywords = []
        for word in keywords:
            if word not in seen:
                seen.add(word)
                unique_keywords.append(word)

        return unique_keywords

    def _extract_category_hints(self, text: str) -> List[str]:
        """
        Extract category hints from title.

        Args:
            text: Product title

        Returns:
            List of detected category hints
        """
        text_lower = text.lower()
        hints = []

        if any(
            word in text_lower
            for word in [
                "phone",
                "iphone",
                "smartphone",
                "tablet",
                "ipad",
                "laptop",
                "computer",
                "monitor",
                "keyboard",
                "mouse",
            ]
        ):
            hints.append("electronics")

        if any(
            word in text_lower
            for word in [
                "headphones",
                "earbuds",
                "earphones",
                "speaker",
                "audio",
                "bluetooth",
            ]
        ):
            hints.append("audio")

        if any(
            word in text_lower
            for word in ["case", "cover", "charger", "cable", "adapter"]
        ):
            hints.append("accessories")

        if any(
            word in text_lower
            for word in ["shirt", "pants", "shoes", "dress", "jacket"]
        ):
            hints.append("clothing")

        return hints