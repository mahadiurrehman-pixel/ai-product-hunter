"""
Query understanding without AI.

Parses raw user search queries into structured SearchIntent objects
using dictionaries, regex, and vocabulary matching.

Design rules:
- No LLM, no embeddings, no paid APIs
- Deterministic: same input → same output
- Transparent: every extraction has a documented reason
- Conservative: when uncertain, preserve the original query
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

from utils.logger import get_logger

logger = get_logger(__name__)

_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


@dataclass
class SearchIntent:
    """
    Structured representation of a user's search query.

    Every field is extracted using deterministic rules.
    Fields that cannot be determined are None, not guessed.
    """

    raw_query: str
    normalized_query: str
    product_type: Optional[str] = None
    product_type_confidence: str = "none"  # high/medium/low/none
    brand: Optional[str] = None
    model: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)
    category: Optional[str] = None
    condition: Optional[str] = None  # new/used/refurbished/None
    exclusions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "raw_query": self.raw_query,
            "normalized_query": self.normalized_query,
            "product_type": self.product_type,
            "product_type_confidence": self.product_type_confidence,
            "brand": self.brand,
            "model": self.model,
            "keywords": self.keywords,
            "attributes": self.attributes,
            "category": self.category,
            "condition": self.condition,
            "exclusions": self.exclusions,
        }


class QueryParser:
    """
    Parses raw search queries into structured SearchIntent.

    Loads product types and brands from YAML config files.
    Uses word-boundary matching for accuracy.
    Handles aliases and common misspellings.
    """

    # Condition keywords (extracted before normalization)
    CONDITION_PATTERNS = {
        "brand new": "new",
        "factory sealed": "new",
        "sealed": "new",
        "new": "new",
        "used": "used",
        "pre-owned": "used",
        "preowned": "used",
        "pre owned": "used",
        "refurbished": "refurbished",
        "renewed": "refurbished",
        "certified refurbished": "refurbished",
        "like new": "used",
        "mint": "used",
        "open box": "used",
    }

    # Common query aliases (normalize before parsing)
    QUERY_ALIASES = {
        "air pods": "airpods",
        "air pod": "airpods",
        "i phone": "iphone",
        "i pad": "ipad",
        "mac book": "macbook",
        "go pro": "gopro",
        "play station": "playstation",
        "x box": "xbox",
        "e cigarette": "e-cigarette",
        "usb c": "usb-c",
        "type c": "type-c",
        "blue tooth": "bluetooth",
        "wi fi": "wifi",
        "wi-fi": "wifi",
    }

    # Exclusion patterns
    EXCLUSION_PATTERN = re.compile(
        r"(?:not|no|without|exclude|excluding|-)\s+(\w+)",
        re.IGNORECASE,
    )

    # Model number patterns
    MODEL_PATTERNS = [
        # AirPods Pro 2, AirPods Pro Max, AirPods 3rd Gen
        re.compile(
            r"\b(airpods\s*(?:pro\s*max|pro)?\s*"
            r"(?:\d+(?:st|nd|rd|th)\s*gen(?:eration)?|\d+)?)\b",
            re.IGNORECASE,
        ),
        # iPhone 15 Pro Max, Galaxy S24 Ultra, Pixel 8 Pro
        re.compile(
            r"\b((?:iphone|galaxy(?:\s+[a-z]+)?|pixel|oneplus|moto(?:\s+[a-z]+)?)\s*"
            r"\d+\s*(?:pro\s*max|ultra|plus|pro|se|mini|lite|e|a|fe)?)\b",
            re.IGNORECASE,
        ),
        # WH-1000XM5, RTX 4070
        re.compile(
            r"\b([A-Z]{2,}-?\d{3,}[A-Z]*\d*)\b",
        ),
        # RTX 4070, GTX 1080
        re.compile(
            r"\b((?:rtx|gtx|rx|ryzen|core\s*i)\s*\d{3,}(?:\s*ti)?)\b",
            re.IGNORECASE,
        ),
        # Generation patterns: 2nd gen, 3rd generation
        re.compile(
            r"\b(\d+(?:st|nd|rd|th)\s*gen(?:eration)?)\b",
            re.IGNORECASE,
        ),
    ]

    # Connectivity attributes
    CONNECTIVITY_PATTERN = re.compile(
        r"\b(bluetooth|wifi|wireless|wired|usb|usb-c|"
        r"lightning|hdmi|type-c|nfc|5g|4g|lte)\b",
        re.IGNORECASE,
    )

    # Wattage/power
    WATTAGE_PATTERN = re.compile(
        r"\b(\d+)\s*w(?:att)?s?\b", re.IGNORECASE
    )

    # Capacity (mAh, ml, oz, etc.)
    CAPACITY_PATTERN = re.compile(
        r"\b(\d+)\s*(mah|ml|oz|l|liter)\b", re.IGNORECASE
    )

    # Pack quantity
    PACK_PATTERN = re.compile(
        r"\b(\d+)\s*(?:pack|pcs|pieces|count|ct|set of)\b",
        re.IGNORECASE,
    )

    def __init__(self):
        """Load vocabularies from config files."""
        self._product_types = self._load_product_types()
        self._brands = self._load_brands()
        self._brand_alias_map = self._build_alias_map()
        self._product_type_alias_map = self._build_product_type_alias_map()

    def parse(self, query: str) -> SearchIntent:
        """
        Parse raw query into structured SearchIntent.

        Args:
            query: Raw user search string

        Returns:
            SearchIntent with extracted components
        """
        if not query or not query.strip():
            return SearchIntent(
                raw_query="",
                normalized_query="",
            )

        raw = query.strip()

        # Step 1: Extract exclusions before normalization
        exclusions = self._extract_exclusions(raw)

        # Step 2: Extract condition before normalization
        condition = self._extract_condition(raw)

        # Step 3: Apply aliases
        normalized = self._apply_aliases(raw.lower())

        # Step 4: Clean text (keep alphanumeric + hyphens + spaces)
        normalized = re.sub(r"[^a-z0-9\s\-]", " ", normalized)
        normalized = " ".join(normalized.split())

        # Step 5: Extract brand
        brand = self._extract_brand(normalized)

        # Step 6: Extract product type
        product_type, pt_confidence, category = self._extract_product_type(
            normalized
        )

        # Step 7: Extract model
        model = self._extract_model(raw)

        # Step 8: Extract attributes
        attributes = self._extract_attributes(raw)

        # Step 9: Extract keywords (remaining meaningful words)
        keywords = self._extract_keywords(normalized)

        return SearchIntent(
            raw_query=raw,
            normalized_query=normalized,
            product_type=product_type,
            product_type_confidence=pt_confidence,
            brand=brand,
            model=model,
            keywords=keywords,
            attributes=attributes,
            category=category,
            condition=condition,
            exclusions=exclusions,
        )

    def _load_product_types(self) -> dict:
        """Load product type vocabulary from YAML."""
        path = _CONFIG_DIR / "product_types.yaml"
        if not path.exists():
            logger.warning(f"Product types config not found: {path}")
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load product types: {e}")
            return {}

    def _load_brands(self) -> dict:
        """Load brand database from YAML."""
        path = _CONFIG_DIR / "brands.yaml"
        if not path.exists():
            logger.warning(f"Brands config not found: {path}")
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load brands: {e}")
            return {}

    def _build_alias_map(self) -> Dict[str, str]:
        """Build alias → canonical brand name mapping."""
        mapping = {}
        for canonical, data in self._brands.items():
            if isinstance(data, dict):
                for alias in data.get("aliases", []):
                    mapping[alias.lower()] = canonical
        return mapping

    def _build_product_type_alias_map(self) -> Dict[str, tuple]:
        """Build alias → (product_type, category, priority) mapping."""
        mapping = {}
        for pt_name, data in self._product_types.items():
            if isinstance(data, dict):
                category = data.get("category", "")
                priority = data.get("priority", 50)
                for alias in data.get("aliases", []):
                    key = alias.lower()
                    if key not in mapping or priority > mapping[key][2]:
                        mapping[key] = (pt_name, category, priority)
        return mapping

    def _apply_aliases(self, text: str) -> str:
        """Replace known aliases in text."""
        for alias, canonical in self.QUERY_ALIASES.items():
            text = text.replace(alias, canonical)
        return text

    def _extract_exclusions(self, text: str) -> List[str]:
        """Extract exclusion terms (e.g., 'not refurbished')."""
        exclusions = []
        for match in self.EXCLUSION_PATTERN.finditer(text):
            exclusions.append(match.group(1).lower())
        return exclusions

    def _extract_condition(self, text: str) -> Optional[str]:
        """Extract product condition from query."""
        text_lower = text.lower()
        for pattern, condition in sorted(
            self.CONDITION_PATTERNS.items(),
            key=lambda x: len(x[0]),
            reverse=True,
        ):
            if pattern in text_lower:
                return condition
        return None

    def _extract_brand(self, normalized: str) -> Optional[str]:
        """
        Extract brand using word-boundary matching against brand aliases.

        Returns canonical brand name or None.
        """
        for alias in sorted(
            self._brand_alias_map.keys(),
            key=len,
            reverse=True,
        ):
            pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
            if re.search(pattern, normalized):
                return self._brand_alias_map[alias]
        return None

    def _extract_product_type(
        self, normalized: str
    ) -> tuple[Optional[str], str, Optional[str]]:
        """
        Extract product type from query.

        Returns:
            (product_type, confidence, category)
        """
        best_match = None
        best_priority = -1
        best_len = 0

        for alias in sorted(
            self._product_type_alias_map.keys(),
            key=len,
            reverse=True,
        ):
            pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
            if re.search(pattern, normalized):
                pt_name, category, priority = (
                    self._product_type_alias_map[alias]
                )
                if priority > best_priority or (
                    priority == best_priority and len(alias) > best_len
                ):
                    best_match = (pt_name, category, priority)
                    best_priority = priority
                    best_len = len(alias)

        if best_match:
            pt_name, category, priority = best_match
            confidence = (
                "high" if priority >= 80
                else "medium" if priority >= 60
                else "low"
            )
            return pt_name, confidence, category

        return None, "none", None

    def _extract_model(self, raw_query: str) -> Optional[str]:
        """Extract model number/name from query."""
        for pattern in self.MODEL_PATTERNS:
            match = pattern.search(raw_query)
            if match:
                return match.group(1).strip()
        return None

    def _extract_attributes(self, raw_query: str) -> Dict[str, str]:
        """Extract structured attributes from query."""
        attrs = {}

        # Connectivity
        conn_match = self.CONNECTIVITY_PATTERN.search(raw_query)
        if conn_match:
            attrs["connectivity"] = conn_match.group(1).lower()

        # Wattage
        watt_match = self.WATTAGE_PATTERN.search(raw_query)
        if watt_match:
            attrs["wattage"] = f"{watt_match.group(1)}W"

        # Capacity
        cap_match = self.CAPACITY_PATTERN.search(raw_query)
        if cap_match:
            attrs["capacity"] = (
                f"{cap_match.group(1)}{cap_match.group(2).lower()}"
            )

        # Pack quantity
        pack_match = self.PACK_PATTERN.search(raw_query)
        if pack_match:
            attrs["quantity"] = pack_match.group(1)

        return attrs

    def _extract_keywords(self, normalized: str) -> List[str]:
        """
        Extract remaining meaningful keywords.

        Filters: min 2 chars, not pure digits, deduplicated.
        """
        words = normalized.split()
        seen: Set[str] = set()
        keywords = []
        for word in words:
            if len(word) >= 2 and not word.isdigit() and word not in seen:
                seen.add(word)
                keywords.append(word)
        return keywords