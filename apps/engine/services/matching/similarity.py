"""
Similarity calculations for product matching (Hardened).

Provides:
- TextSimilarity: Jaccard on keywords + boosts
- AttributeSimilarity: unit-aware canonical comparison
- CompatibilitySimilarity: accessory/device compatibility
- IdentifierSimilarity: MPN/UPC/EAN/GTIN matching
- ConditionSimilarity: condition comparison
- VariantSimilarity: variant-level comparison
"""
from typing import Dict, List, Optional, Set, Tuple

from utils.logger import get_logger
from services.product_identity.models import ProductIdentity
from services.product_identity.attributes import (
    AttributeStatus,
    CanonicalAttribute,
)
from services.product_identity.taxonomy import TaxonomyEngine

logger = get_logger(__name__)
_taxonomy = TaxonomyEngine()


class TextSimilarity:
    """Jaccard similarity on normalized keywords + boosts."""

    MODEL_BOOST = 0.15
    FAMILY_BOOST = 0.05
    GENERATION_BOOST = 0.05

    def calculate(
        self,
        identity_a: ProductIdentity,
        identity_b: ProductIdentity,
    ) -> Tuple[float, List[str]]:
        keywords_a = set(k.lower() for k in (identity_a.keywords or []))
        keywords_b = set(k.lower() for k in (identity_b.keywords or []))

        if not keywords_a and not keywords_b:
            return 0.0, []

        union = keywords_a | keywords_b
        if not union:
            return 0.0, []

        intersection = keywords_a & keywords_b
        jaccard = len(intersection) / len(union)

        boost = 0.0
        if identity_a.model and identity_b.model:
            ma, mb = identity_a.model.lower(), identity_b.model.lower()
            if ma == mb:
                boost += self.MODEL_BOOST
            elif ma in mb or mb in ma:
                boost += self.MODEL_BOOST * 0.5

        if identity_a.model_family and identity_b.model_family:
            if identity_a.model_family.lower() == identity_b.model_family.lower():
                boost += self.FAMILY_BOOST

        if identity_a.generation and identity_b.generation:
            if identity_a.generation.lower() == identity_b.generation.lower():
                boost += self.GENERATION_BOOST

        return round(min(1.0, jaccard + boost), 4), sorted(intersection)


class AttributeSimilarity:
    """Unit-aware canonical attribute comparison."""

    NUMERIC_TOLERANCE = 0.01

    def calculate(
        self,
        identity_a: ProductIdentity,
        identity_b: ProductIdentity,
    ) -> Tuple[float, List[str], List[str]]:
        attrs_a = {a.name: a for a in (identity_a.canonical_attributes or [])}
        attrs_b = {a.name: a for a in (identity_b.canonical_attributes or [])}

        if not attrs_a and not attrs_b:
            return 0.5, [], []

        common = set(attrs_a.keys()) & set(attrs_b.keys())
        if not common:
            return 0.5, [], []

        matching, differing = [], []
        total_score, compared = 0.0, 0

        for key in sorted(common):
            a, b = attrs_a[key], attrs_b[key]
            compared += 1

            if a.status == AttributeStatus.UNKNOWN or b.status == AttributeStatus.UNKNOWN:
                total_score += 0.3
                continue
            if a.status == AttributeStatus.CONFLICT or b.status == AttributeStatus.CONFLICT:
                total_score += 0.2
                differing.append(f"{key}: conflicting values")
                continue

            if self._values_match(a, b):
                total_score += 1.0
                matching.append(f"{key}: {a.normalized_value or a.raw_value}")
            else:
                differing.append(
                    f"{key}: '{a.normalized_value or a.raw_value}' vs "
                    f"'{b.normalized_value or b.raw_value}'"
                )

        if compared == 0:
            return 0.5, matching, differing

        return round(total_score / compared, 4), matching, differing

    def _values_match(self, a: CanonicalAttribute, b: CanonicalAttribute) -> bool:
        if (a.normalized_value and b.normalized_value
                and a.normalized_value == b.normalized_value):
            return True
        if a.numeric_value is not None and b.numeric_value is not None:
            if a.numeric_value == 0 and b.numeric_value == 0:
                return True
            if a.numeric_value != 0:
                if abs(a.numeric_value - b.numeric_value) / abs(a.numeric_value) <= self.NUMERIC_TOLERANCE:
                    return True
        if (a.raw_value and b.raw_value
                and a.raw_value.lower().strip() == b.raw_value.lower().strip()):
            return True
        return False


class CompatibilitySimilarity:
    """
    Compatibility comparison using compatible_models and product roles.

    CRITICAL RULE: Compatibility ≠ Identity.
    A phone case compatible with iPhone 15 is NOT the same product
    as an iPhone 15. High compatibility between different product
    roles should NOT inflate the match score.

    Returns (score, evidence_list).
    """

    def calculate(
        self,
        identity_a: ProductIdentity,
        identity_b: ProductIdentity,
    ) -> Tuple[float, List[str]]:
        evidence = []

        # Both devices — no compatibility check needed
        if not identity_a.is_accessory and not identity_b.is_accessory:
            return 0.5, ["Both are devices — compatibility not applicable"]

        # One accessory, one device — fundamentally different products
        # Even if compatible, they are NOT the same product
        if identity_a.is_accessory != identity_b.is_accessory:
            accessory = identity_a if identity_a.is_accessory else identity_b
            device = identity_b if identity_a.is_accessory else identity_a

            if self._is_compatible(accessory, device):
                evidence.append(
                    f"Accessory compatible with "
                    f"{device.model or device.product_type}, "
                    f"but they are different product types"
                )
                # LOW score: compatible but fundamentally different products
                return 0.15, evidence
            else:
                evidence.append(
                    f"Accessory NOT compatible with "
                    f"{device.model or device.product_type}"
                )
                return 0.05, evidence

        # Both accessories — check if they target the same devices
        if identity_a.is_accessory and identity_b.is_accessory:
            # Same product type = good sign
            if (
                identity_a.product_type
                and identity_b.product_type
                and identity_a.product_type == identity_b.product_type
            ):
                compat_a = set(
                    m.lower() for m in (identity_a.compatible_models or [])
                )
                compat_b = set(
                    m.lower() for m in (identity_b.compatible_models or [])
                )

                if not compat_a and not compat_b:
                    return 0.7, ["Same accessory type, no compatibility info"]

                if compat_a and compat_b:
                    overlap = compat_a & compat_b
                    if overlap:
                        evidence.append(
                            f"Both compatible with: "
                            f"{', '.join(list(overlap)[:3])}"
                        )
                        return 0.9, evidence
                    else:
                        evidence.append(
                            "Same accessory type but target different devices"
                        )
                        return 0.3, evidence

                return 0.6, ["Same accessory type, partial compatibility info"]

            # Different accessory types
            return 0.3, ["Different accessory types"]

        return 0.5, []

    def _is_compatible(
        self, accessory: ProductIdentity, device: ProductIdentity
    ) -> bool:
        if accessory.compatible_models and device.model:
            dm = device.model.lower()
            for c in accessory.compatible_models:
                if dm in c.lower() or c.lower() in dm:
                    return True
        if accessory.compatible_categories and device.product_type:
            if device.product_type in accessory.compatible_categories:
                return True
        return False


class IdentifierSimilarity:
    """
    Exact identifier matching (MPN, UPC, EAN, GTIN, Part Number).

    Returns (score, evidence_list).
    1.0 = exact match, 0.0 = conflict, 0.5 = no identifiers to compare.
    """

    IDENTIFIER_KEYS = {"mpn", "upc", "ean", "gtin", "part_number", "sku"}

    def calculate(
        self,
        identity_a: ProductIdentity,
        identity_b: ProductIdentity,
    ) -> Tuple[float, List[str]]:
        ids_a = self._extract_identifiers(identity_a)
        ids_b = self._extract_identifiers(identity_b)

        if not ids_a and not ids_b:
            return 0.5, ["No identifiers available for comparison"]

        common_keys = set(ids_a.keys()) & set(ids_b.keys())
        if not common_keys:
            return 0.5, ["No common identifier types"]

        matches, conflicts = [], []
        for key in common_keys:
            va = self._normalize_id(ids_a[key])
            vb = self._normalize_id(ids_b[key])
            if va and vb:
                if va == vb:
                    matches.append(f"{key}: {va}")
                else:
                    conflicts.append(f"{key}: {va} vs {vb}")

        if conflicts:
            return 0.0, [f"Identifier conflict: {c}" for c in conflicts]
        if matches:
            return 1.0, [f"Identifier match: {m}" for m in matches]

        return 0.5, ["Identifiers present but not comparable"]

    def _extract_identifiers(
        self, identity: ProductIdentity
    ) -> Dict[str, str]:
        result = {}
        for attr in (identity.canonical_attributes or []):
            if attr.name.lower() in self.IDENTIFIER_KEYS:
                val = attr.normalized_value or attr.raw_value
                if val:
                    result[attr.name.lower()] = str(val)
        return result

    def _normalize_id(self, value: str) -> str:
        return value.strip().upper().replace("-", "").replace(" ", "")


class ConditionSimilarity:
    """
    Condition comparison.

    Returns (score, evidence_list).
    """

    CONDITION_RANK = {
        "new": 4,
        "open_box": 3,
        "refurbished": 2,
        "used": 1,
        "unknown": 0,
    }

    def calculate(
        self,
        identity_a: ProductIdentity,
        identity_b: ProductIdentity,
    ) -> Tuple[float, List[str]]:
        cond_a = (identity_a.condition or "unknown").lower().strip()
        cond_b = (identity_b.condition or "unknown").lower().strip()

        if cond_a == "unknown" and cond_b == "unknown":
            return 0.5, ["Condition unknown for both products"]

        if cond_a == "unknown" or cond_b == "unknown":
            return 0.5, [f"Condition unknown for one product ({cond_a} vs {cond_b})"]

        if cond_a == cond_b:
            return 1.0, [f"Same condition: {cond_a}"]

        rank_a = self.CONDITION_RANK.get(cond_a, 0)
        rank_b = self.CONDITION_RANK.get(cond_b, 0)
        diff = abs(rank_a - rank_b)

        if diff == 1:
            return 0.6, [f"Condition differs slightly: {cond_a} vs {cond_b}"]
        elif diff == 2:
            return 0.3, [f"Condition differs: {cond_a} vs {cond_b}"]
        else:
            return 0.1, [f"Condition mismatch: {cond_a} vs {cond_b}"]


class VariantSimilarity:
    """
    Variant-level comparison.

    Compares model, generation, storage, RAM, connectivity, etc.
    Returns (score, matches, conflicts).
    """

    VARIANT_ATTRS = [
        "storage", "memory", "connectivity", "size",
        "color", "capacity", "voltage", "length",
    ]

    def calculate(
        self,
        identity_a: ProductIdentity,
        identity_b: ProductIdentity,
    ) -> Tuple[float, List[str], List[str]]:
        matches, conflicts = [], []

        # Model comparison
        if identity_a.model and identity_b.model:
            ma, mb = identity_a.model.lower(), identity_b.model.lower()
            if ma == mb:
                matches.append(f"model: {identity_a.model}")
            elif ma in mb or mb in ma:
                matches.append(f"model: partial ({ma} vs {mb})")
            else:
                conflicts.append(f"model: {identity_a.model} vs {identity_b.model}")

        # Generation
        if identity_a.generation and identity_b.generation:
            ga, gb = identity_a.generation.lower(), identity_b.generation.lower()
            if ga == gb:
                matches.append(f"generation: {identity_a.generation}")
            else:
                conflicts.append(
                    f"generation: {identity_a.generation} vs {identity_b.generation}"
                )

        # Canonical attributes
        attrs_a = {
            a.name: a for a in (identity_a.canonical_attributes or [])
            if a.name in self.VARIANT_ATTRS
        }
        attrs_b = {
            a.name: a for a in (identity_b.canonical_attributes or [])
            if a.name in self.VARIANT_ATTRS
        }

        for key in set(attrs_a.keys()) & set(attrs_b.keys()):
            a, b = attrs_a[key], attrs_b[key]
            if a.status == AttributeStatus.UNKNOWN or b.status == AttributeStatus.UNKNOWN:
                continue
            nv_a = a.normalized_value or a.raw_value
            nv_b = b.normalized_value or b.raw_value
            if nv_a and nv_b:
                if nv_a.lower() == nv_b.lower():
                    matches.append(f"{key}: {nv_a}")
                elif (a.numeric_value is not None and b.numeric_value is not None
                      and a.numeric_value != 0
                      and abs(a.numeric_value - b.numeric_value) / abs(a.numeric_value) <= 0.01):
                    matches.append(f"{key}: {nv_a} ≈ {nv_b}")
                else:
                    conflicts.append(f"{key}: {nv_a} vs {nv_b}")

        total = len(matches) + len(conflicts)
        if total == 0:
            return 0.5, matches, conflicts

        score = len(matches) / total
        return round(score, 4), matches, conflicts
class QuantitySimilarity:
    """
    Quantity and pack comparison (Pre-Phase 6.5).

    Uses BundleDetector to compare quantities between products.
    """

    def __init__(self):
        from .bundle_detector import BundleDetector
        self._detector = BundleDetector()

    def calculate(
        self,
        identity_a: "ProductIdentity",
        identity_b: "ProductIdentity",
    ) -> Tuple[float, List[str]]:
        """
        Compare quantity/pack between two product identities.

        Returns:
            Tuple of (similarity 0.0-1.0, evidence_list)
        """
        title_a = identity_a.original_title or ""
        title_b = identity_b.original_title or ""

        score, explanation = self._detector.compare(title_a, title_b)
        return score, [explanation]