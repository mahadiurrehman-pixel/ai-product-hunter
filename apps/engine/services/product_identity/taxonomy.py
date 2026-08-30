"""
Canonical Product Taxonomy Engine.

Provides deterministic product type resolution, role classification,
category path computation, and relationship lookup from a
configuration-driven taxonomy.

Design rules:
- Configuration-driven: add new types via product_types.yaml
- Deterministic: same input → same output
- Priority-based resolution: higher priority type wins conflicts
- Role-aware: device vs accessory vs replacement_part etc.
- Does NOT implement matching or similarity scoring
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

from utils.logger import get_logger

logger = get_logger(__name__)

_CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


@dataclass
class ProductTypeInfo:
    """Canonical information about a product type."""

    name: str                          # canonical name (e.g., "phone_case")
    category: str                      # parent category (e.g., "accessories")
    priority: int                      # higher = more specific
    parent: str                        # taxonomy parent node
    role: str                          # device|accessory|replacement_part|...
    compatible_categories: List[str] = field(default_factory=list)
    related_types: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)

    @property
    def is_device(self) -> bool:
        return self.role == "device"

    @property
    def is_accessory(self) -> bool:
        return self.role in ("accessory", "replacement_part", "consumable")

    @property
    def category_path(self) -> List[str]:
        """Canonical category path from root to this type."""
        hierarchy = {
            "devices": ["electronics", "devices"],
            "accessories": ["electronics", "accessories"],
            "peripherals": ["electronics", "peripherals"],
            "storage": ["electronics", "storage"],
            "replacement_parts": ["electronics", "replacement_parts"],
            "consumables": ["electronics", "consumables"],
            "bundles": ["electronics", "bundles"],
            "home": ["home"],
        }
        base = hierarchy.get(self.parent, [self.parent])
        return base + [self.name]


class TaxonomyEngine:
    """
    Configuration-driven product taxonomy engine.

    Loads product_types.yaml and provides:
    - Type resolution from title text
    - Role classification
    - Category path computation
    - Relationship lookup

    Usage:
        engine = TaxonomyEngine()
        info = engine.resolve_type("iPhone 15 Case")
        # info.name == "phone_case"
        # info.role == "accessory"
        # info.compatible_categories == ["smartphone"]
    """

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or (_CONFIG_DIR / "product_types.yaml")
        self._types: Dict[str, ProductTypeInfo] = {}
        self._alias_map: Dict[str, str] = {}  # alias → canonical name
        self._load()

    def _load(self) -> None:
        """Load taxonomy from YAML config."""
        if not self._config_path.exists():
            logger.warning(f"Taxonomy config not found: {self._config_path}")
            return

        try:
            with open(self._config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load taxonomy: {e}")
            return

        for type_name, config in data.items():
            if not isinstance(config, dict):
                continue

            info = ProductTypeInfo(
                name=type_name,
                category=config.get("category", "unknown"),
                priority=config.get("priority", 50),
                parent=config.get("parent", "unknown"),
                role=config.get("role", "unknown"),
                compatible_categories=config.get(
                    "compatible_categories", []
                ),
                related_types=config.get("related_types", []),
                aliases=config.get("aliases", []),
            )
            self._types[type_name] = info

            # Build alias map (longer aliases first for priority)
            for alias in info.aliases:
                key = alias.lower().strip()
                # Higher priority type wins alias conflicts
                if key not in self._alias_map:
                    self._alias_map[key] = type_name
                else:
                    existing = self._types[self._alias_map[key]]
                    if info.priority > existing.priority:
                        self._alias_map[key] = type_name

        logger.info(
            f"Loaded {len(self._types)} product types, "
            f"{len(self._alias_map)} aliases"
        )

    def resolve_type(self, title: str) -> Optional[ProductTypeInfo]:
        """
        Resolve the canonical product type from a title string.

        Uses word-boundary matching against all aliases.
        When multiple types match, highest priority wins.

        Args:
            title: Product title string

        Returns:
            ProductTypeInfo or None if no type detected
        """
        if not title or not title.strip():
            return None

        title_lower = title.lower()
        candidates: List[Tuple[int, str]] = []

        for alias, type_name in self._alias_map.items():
            pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
            if re.search(pattern, title_lower):
                info = self._types[type_name]
                candidates.append((info.priority, type_name))

        if not candidates:
            return None

        # Highest priority wins
        candidates.sort(key=lambda x: x[0], reverse=True)
        best_type = candidates[0][1]
        return self._types[best_type]

    def get_type(self, type_name: str) -> Optional[ProductTypeInfo]:
        """Get ProductTypeInfo by canonical name."""
        return self._types.get(type_name)

    def get_role(self, type_name: str) -> str:
        """Get the product role for a type name."""
        info = self._types.get(type_name)
        return info.role if info else "unknown"

    def get_category_path(self, type_name: str) -> List[str]:
        """Get the canonical category path for a type."""
        info = self._types.get(type_name)
        return info.category_path if info else [type_name]

    def get_compatible_categories(self, type_name: str) -> List[str]:
        """Get compatible device categories for an accessory type."""
        info = self._types.get(type_name)
        return info.compatible_categories if info else []

    def get_related_types(self, type_name: str) -> List[str]:
        """Get related product types."""
        info = self._types.get(type_name)
        return info.related_types if info else []

    def is_accessory_type(self, type_name: str) -> bool:
        """Check if a type is an accessory role."""
        info = self._types.get(type_name)
        return info.is_accessory if info else False

    def all_types(self) -> List[str]:
        """Get all canonical type names."""
        return list(self._types.keys())

    def types_by_role(self, role: str) -> List[str]:
        """Get all types with a specific role."""
        return [
            name for name, info in self._types.items()
            if info.role == role
        ]

    def types_by_category(self, category: str) -> List[str]:
        """Get all types in a category."""
        return [
            name for name, info in self._types.items()
            if info.category == category
        ]