"""
Universal Canonical Attribute System.

Provides deterministic normalization of product attributes into a
consistent, marketplace-independent canonical representation.

Integrates with UnitConverter for robust unit normalization.

Design rules:
- Rule-based only, no AI/LLM
- Deterministic: same input → same output
- Raw values ALWAYS preserved alongside normalized values
- Missing ≠ Unknown: explicitly distinguished
- Conflicts preserved, not silently resolved
- Extensible: new attributes via config, not code changes
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .units import UnitConverter, UnitConversionResult


class AttributeConfidence(str, Enum):
    """How confidently the attribute was extracted."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AttributeStatus(str, Enum):
    """Status of an attribute's normalization."""

    NORMALIZED = "normalized"
    UNKNOWN = "unknown"
    CONFLICT = "conflict"


@dataclass
class CanonicalAttribute:
    """
    A single canonical product attribute.

    Preserves both the raw source value and the normalized form.
    Never fabricates a normalized value — if uncertain, status=UNKNOWN.
    """

    name: str
    raw_value: str
    normalized_value: Optional[str] = None
    unit: Optional[str] = None
    original_unit: Optional[str] = None
    numeric_value: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    is_approximate: bool = False
    source: str = "title"
    confidence: AttributeConfidence = AttributeConfidence.MEDIUM
    status: AttributeStatus = AttributeStatus.NORMALIZED
    conflict_values: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "unit": self.unit,
            "original_unit": self.original_unit,
            "numeric_value": self.numeric_value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "is_approximate": self.is_approximate,
            "source": self.source,
            "confidence": self.confidence.value,
            "status": self.status.value,
            "conflict_values": self.conflict_values,
        }


# =============================================================================
# Centralized Alias System
# =============================================================================

ATTRIBUTE_NAME_ALIASES: Dict[str, str] = {
    "color": "color", "colour": "color", "col": "color",
    "memory": "memory", "ram": "memory", "ram size": "memory",
    "storage": "storage", "capacity": "storage",
    "internal storage": "storage", "disk size": "storage",
    "storage capacity": "storage", "ssd": "storage", "hdd": "storage",
    "connectivity": "connectivity", "connection": "connectivity",
    "wireless": "connectivity", "interface": "connectivity",
    "size": "size", "dimensions": "size",
    "screen size": "size", "display size": "size",
    "battery_capacity": "battery_capacity",
    "battery capacity": "battery_capacity", "battery": "battery_capacity",
    "wattage": "wattage", "power": "wattage", "watts": "wattage",
    "pack_quantity": "pack_quantity", "pack": "pack_quantity",
    "quantity": "pack_quantity", "count": "pack_quantity",
    "pieces": "pack_quantity", "pcs": "pack_quantity",
    "weight": "weight",
    "voltage": "voltage",
    "current": "current",
    "frequency": "frequency",
}


# =============================================================================
# Color Normalization
# =============================================================================

COLOR_CANONICAL: Dict[str, str] = {
    "black": "black", "white": "white", "red": "red", "blue": "blue",
    "green": "green", "yellow": "yellow", "orange": "orange",
    "purple": "purple", "pink": "pink", "gray": "gray", "grey": "gray",
    "brown": "brown", "silver": "silver", "gold": "gold",
    "navy": "navy", "navy blue": "navy", "beige": "beige",
    "bronze": "bronze", "rose gold": "rose_gold",
    "space gray": "space_gray", "space grey": "space_gray",
    "midnight": "midnight", "natural titanium": "titanium",
    "titanium": "titanium", "coral": "coral", "cream": "cream",
    "lavender": "lavender", "mint": "mint", "teal": "teal",
    "burgundy": "burgundy",
}


# =============================================================================
# Connectivity Normalization
# =============================================================================

CONNECTIVITY_CANONICAL: Dict[str, str] = {
    "bluetooth": "bluetooth", "bluetooth 5.0": "bluetooth_5.0",
    "bluetooth 5.1": "bluetooth_5.1", "bluetooth 5.2": "bluetooth_5.2",
    "bluetooth 5.3": "bluetooth_5.3", "bt": "bluetooth",
    "wifi": "wifi", "wi-fi": "wifi", "wi fi": "wifi",
    "wifi 6": "wifi_6", "wifi 6e": "wifi_6e",
    "usb": "usb", "usb-c": "usb-c", "usb c": "usb-c",
    "type-c": "usb-c", "type c": "usb-c",
    "lightning": "lightning", "hdmi": "hdmi", "nfc": "nfc",
    "wired": "wired", "wireless": "wireless",
    "5g": "5g", "4g": "4g", "lte": "lte",
    "3.5mm": "3.5mm_jack", "aux": "3.5mm_jack",
}


# =============================================================================
# Attribute → Unit Family Mapping
# =============================================================================

# Maps canonical attribute names to their unit family for conversion
ATTRIBUTE_UNIT_FAMILY = {
    "storage": "storage",
    "memory": "storage",  # Same conversion table as storage
    "size": "length",
    "battery_capacity": "battery",
    "wattage": "power",
    "weight": "weight",
    "voltage": "voltage",
    "current": "current",
    "frequency": "frequency",
}


# =============================================================================
# Regex Patterns (for attributes without unit conversion)
# =============================================================================

STORAGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mb|gb|tb)\b", re.IGNORECASE
)
SIZE_PATTERN = re.compile(
    r'(\d+(?:\.\d+)?)\s*(inch(?:es)?|in|cm|mm|")', re.IGNORECASE
)
WATTAGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:w|watt|watts)\b", re.IGNORECASE
)
CAPACITY_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mah|ml|oz|l|liter|litre)\b", re.IGNORECASE
)


class AttributeNormalizer:
    """
    Normalizes raw product attributes into canonical form.

    Uses UnitConverter for robust unit parsing and conversion.
    """

    def __init__(self):
        self._unit_converter = UnitConverter()

    def normalize_all(
        self,
        raw_attributes: Dict[str, str],
        source: str = "title",
        confidence: AttributeConfidence = AttributeConfidence.MEDIUM,
    ) -> List[CanonicalAttribute]:
        """Normalize a dictionary of raw attributes."""
        if not raw_attributes:
            return []

        results = []
        for raw_name, raw_value in raw_attributes.items():
            if not raw_name or not raw_value:
                continue
            canonical = self.normalize_single(
                raw_name, str(raw_value), source, confidence
            )
            if canonical:
                results.append(canonical)
        return results

    def normalize_single(
        self,
        raw_name: str,
        raw_value: str,
        source: str = "title",
        confidence: AttributeConfidence = AttributeConfidence.MEDIUM,
    ) -> Optional[CanonicalAttribute]:
        """Normalize a single attribute name + value pair."""
        canonical_name = self._canonicalize_name(raw_name)

        if canonical_name in ("brand_from_api",):
            return None

        normalized, unit, original_unit, numeric, status, \
            min_val, max_val, is_approx = self._normalize_value(
                canonical_name, raw_value
            )

        return CanonicalAttribute(
            name=canonical_name,
            raw_value=raw_value,
            normalized_value=normalized,
            unit=unit,
            original_unit=original_unit,
            numeric_value=numeric,
            min_value=min_val,
            max_value=max_val,
            is_approximate=is_approx,
            source=source,
            confidence=confidence,
            status=status,
        )

    def merge_with_conflicts(
        self,
        primary: List[CanonicalAttribute],
        secondary: List[CanonicalAttribute],
    ) -> List[CanonicalAttribute]:
        """Merge two attribute lists, detecting conflicts."""
        result = list(primary)
        primary_names = {a.name: a for a in primary}

        for attr in secondary:
            if attr.name in primary_names:
                existing = primary_names[attr.name]
                if (
                    existing.normalized_value
                    and attr.normalized_value
                    and existing.normalized_value != attr.normalized_value
                ):
                    if attr.raw_value not in existing.conflict_values:
                        existing.conflict_values.append(attr.raw_value)
                    existing = CanonicalAttribute(
                        name=existing.name,
                        raw_value=existing.raw_value,
                        normalized_value=existing.normalized_value,
                        unit=existing.unit,
                        original_unit=existing.original_unit,
                        numeric_value=existing.numeric_value,
                        min_value=existing.min_value,
                        max_value=existing.max_value,
                        is_approximate=existing.is_approximate,
                        source=existing.source,
                        confidence=existing.confidence,
                        status=AttributeStatus.CONFLICT,
                        conflict_values=existing.conflict_values,
                    )
                    for i, r in enumerate(result):
                        if r.name == existing.name:
                            result[i] = existing
                            break
            else:
                result.append(attr)
        return result

    def to_flat_dict(
        self,
        canonical_attrs: List[CanonicalAttribute],
    ) -> Dict[str, str]:
        """Convert canonical attributes to flat dict for backward compat."""
        flat = {}
        for attr in canonical_attrs:
            value = attr.normalized_value or attr.raw_value
            if attr.unit and attr.numeric_value is not None:
                nv = attr.numeric_value
                formatted = (
                    str(int(nv)) if nv == int(nv) else str(nv)
                )
                value = f"{formatted}{attr.unit}"
            flat[attr.name] = value
        return flat

    def _canonicalize_name(self, raw_name: str) -> str:
        key = raw_name.lower().strip()
        return ATTRIBUTE_NAME_ALIASES.get(key, key)

    def _normalize_value(
        self,
        canonical_name: str,
        raw_value: str,
    ) -> tuple:
        """
        Normalize value based on attribute type.

        Returns:
            (normalized_value, unit, original_unit, numeric_value,
             status, min_value, max_value, is_approximate)
        """
        raw_lower = raw_value.lower().strip()

        # Check if this attribute has a unit family for conversion
        unit_family = ATTRIBUTE_UNIT_FAMILY.get(canonical_name)

        if unit_family:
            # Use UnitConverter for robust parsing
            result = self._unit_converter.convert(
                raw_value, family=unit_family
            )
            if result.success:
                nv = result.numeric_value
                formatted = (
                    str(int(nv)) if nv is not None and nv == int(nv)
                    else str(nv)
                )
                norm_str = (
                    f"{formatted}{result.canonical_unit}"
                    if result.canonical_unit
                    else formatted
                )
                return (
                    norm_str,
                    result.canonical_unit,
                    result.original_unit,
                    result.numeric_value,
                    AttributeStatus.NORMALIZED,
                    result.min_value,
                    result.max_value,
                    result.is_approximate,
                )
            elif result.numeric_value is not None:
                return (
                    raw_lower,
                    None,
                    result.original_unit,
                    result.numeric_value,
                    AttributeStatus.UNKNOWN,
                    result.min_value,
                    result.max_value,
                    result.is_approximate,
                )
            else:
                return (
                    raw_lower, None, None, None,
                    AttributeStatus.UNKNOWN,
                    None, None, result.is_approximate,
                )

        # Non-unit attributes
        if canonical_name == "color":
            return self._normalize_color(raw_lower)
        elif canonical_name == "connectivity":
            return self._normalize_connectivity(raw_lower)
        elif canonical_name == "pack_quantity":
            return self._normalize_pack_quantity(raw_value)
        else:
            return (
                raw_lower, None, None, None,
                AttributeStatus.NORMALIZED,
                None, None, False,
            )

    def _normalize_color(self, raw_lower):
        canonical = COLOR_CANONICAL.get(raw_lower)
        if canonical:
            return (
                canonical, None, None, None,
                AttributeStatus.NORMALIZED, None, None, False,
            )
        for key, val in sorted(
            COLOR_CANONICAL.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if key in raw_lower:
                return (
                    val, None, None, None,
                    AttributeStatus.NORMALIZED, None, None, False,
                )
        return (
            None, None, None, None,
            AttributeStatus.UNKNOWN, None, None, False,
        )

    def _normalize_connectivity(self, raw_lower):
        canonical = CONNECTIVITY_CANONICAL.get(raw_lower)
        if canonical:
            return (
                canonical, None, None, None,
                AttributeStatus.NORMALIZED, None, None, False,
            )
        for key, val in sorted(
            CONNECTIVITY_CANONICAL.items(),
            key=lambda x: len(x[0]), reverse=True,
        ):
            if key in raw_lower:
                return (
                    val, None, None, None,
                    AttributeStatus.NORMALIZED, None, None, False,
                )
        return (
            None, None, None, None,
            AttributeStatus.UNKNOWN, None, None, False,
        )

    def _normalize_pack_quantity(self, raw_value):
        digits = re.search(r"(\d+)", raw_value)
        if digits:
            val = int(digits.group(1))
            return (
                str(val), None, None, float(val),
                AttributeStatus.NORMALIZED, None, None, False,
            )
        return (
            raw_value.lower().strip(), None, None, None,
            AttributeStatus.UNKNOWN, None, None, False,
        )