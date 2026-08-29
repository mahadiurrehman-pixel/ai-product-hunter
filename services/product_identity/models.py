"""
Product Identity data models.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .attributes import CanonicalAttribute


class DataQuality(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ProductIdentity:
    """
    Canonical product identity.

    Fields:
        product_type: Canonical product type (e.g., "phone_case")
        product_role: Product role (device|accessory|replacement_part|
                      consumable|component|bundle|kit|unknown)
        category_path: Canonical category path (e.g., ["electronics",
                       "accessories", "phone_case"])
        compatible_categories: For accessories, what device categories
                               they support
    """

    # Core identity
    product_type: Optional[str] = None
    product_role: str = "unknown"
    brand: Optional[str] = None
    model: Optional[str] = None
    model_family: Optional[str] = None
    generation: Optional[str] = None
    variant: Optional[str] = None
    compatible_models: List[str] = field(default_factory=list)
    is_accessory: bool = False
    condition: Optional[str] = None
    exclusions: List[str] = field(default_factory=list)

    # Taxonomy
    category_path: List[str] = field(default_factory=list)
    compatible_categories: List[str] = field(default_factory=list)

    # Descriptive
    attributes: Dict[str, str] = field(default_factory=dict)
    canonical_attributes: List = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    # Provenance
    source: str = "unknown"
    marketplace: Optional[str] = None

    # Quality
    identity_confidence: float = 0.0
    data_quality: DataQuality = DataQuality.LOW

    # Traceability
    original_title: str = ""

    @property
    def identity_key(self) -> str:
        parts = [
            (self.brand or "unknown").lower(),
            (self.product_type or "unknown").lower(),
            (self.model or "unknown").lower(),
            (self.variant or "unknown").lower(),
        ]
        return "|".join(parts)

    @property
    def has_attribute_conflicts(self) -> bool:
        from .attributes import AttributeStatus
        return any(
            a.status == AttributeStatus.CONFLICT
            for a in self.canonical_attributes
        )

    def get_canonical_attribute(self, name: str):
        for attr in self.canonical_attributes:
            if attr.name == name:
                return attr
        return None

    def to_dict(self) -> dict:
        return {
            "product_type": self.product_type,
            "product_role": self.product_role,
            "brand": self.brand,
            "model": self.model,
            "model_family": self.model_family,
            "generation": self.generation,
            "variant": self.variant,
            "compatible_models": self.compatible_models,
            "is_accessory": self.is_accessory,
            "condition": self.condition,
            "exclusions": self.exclusions,
            "category_path": self.category_path,
            "compatible_categories": self.compatible_categories,
            "attributes": self.attributes,
            "canonical_attributes": [
                a.to_dict() for a in self.canonical_attributes
            ],
            "has_attribute_conflicts": self.has_attribute_conflicts,
            "keywords": self.keywords,
            "source": self.source,
            "marketplace": self.marketplace,
            "identity_confidence": round(self.identity_confidence, 3),
            "data_quality": self.data_quality.value,
            "identity_key": self.identity_key,
            "original_title": self.original_title,
        }