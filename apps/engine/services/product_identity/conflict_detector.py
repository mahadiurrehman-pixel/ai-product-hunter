"""
Conflict Detector for Product Identity comparison.

Compares two ProductIdentity objects and produces an EvidenceSet
containing positive matches, conflicts, missing data, and unknown values.

CRITICAL DESIGN RULES:
- NEVER produces a match score
- NEVER produces a match decision
- Missing data is NEVER treated as conflict
- Unknown values are NEVER treated as strong conflict
- Only reports factual evidence
- Phase 5 matcher consumes this evidence to MAKE decisions

Usage:
    detector = ConflictDetector()
    evidence = detector.compare(identity_a, identity_b)
    # evidence is an EvidenceSet, NOT a match result
"""
from typing import Optional

from utils.logger import get_logger

from .models import ProductIdentity
from .evidence import (
    ConflictSeverity,
    Evidence,
    EvidenceSet,
    EvidenceStrength,
    EvidenceType,
)

logger = get_logger(__name__)


class ConflictDetector:
    """
    Compares two ProductIdentity objects and produces evidence.

    Does NOT produce match scores.
    Does NOT persist results.
    Does NOT connect to any database.
    """

    def compare(
        self,
        identity_a: ProductIdentity,
        identity_b: ProductIdentity,
    ) -> EvidenceSet:
        """
        Compare two product identities and produce evidence.

        Args:
            identity_a: First product identity
            identity_b: Second product identity

        Returns:
            EvidenceSet with categorized evidence items
        """
        evidence_set = EvidenceSet()

        # Compare each identity dimension
        self._compare_product_type(identity_a, identity_b, evidence_set)
        self._compare_brand(identity_a, identity_b, evidence_set)
        self._compare_model(identity_a, identity_b, evidence_set)
        self._compare_model_family(identity_a, identity_b, evidence_set)
        self._compare_generation(identity_a, identity_b, evidence_set)
        self._compare_variant(identity_a, identity_b, evidence_set)
        self._compare_condition(identity_a, identity_b, evidence_set)
        self._compare_accessory_context(identity_a, identity_b, evidence_set)
        self._compare_canonical_attributes(identity_a, identity_b, evidence_set)

        return evidence_set

    def _compare_product_type(
        self, a: ProductIdentity, b: ProductIdentity, es: EvidenceSet
    ) -> None:
        """Compare product types — strongest identity signal."""
        val_a = a.product_type
        val_b = b.product_type

        if not val_a and not val_b:
            es.missing.append(Evidence(
                field="product_type",
                evidence_type=EvidenceType.MISSING,
                strength=EvidenceStrength.STRONG,
                explanation="Neither identity has a detected product type.",
            ))
            return

        if not val_a or not val_b:
            es.missing.append(Evidence(
                field="product_type",
                evidence_type=EvidenceType.MISSING,
                strength=EvidenceStrength.STRONG,
                value_a=val_a,
                value_b=val_b,
                explanation=(
                    f"Product type missing from one identity: "
                    f"'{val_a or 'missing'}' vs '{val_b or 'missing'}'."
                ),
            ))
            return

        if val_a == val_b:
            es.positive.append(Evidence(
                field="product_type",
                evidence_type=EvidenceType.POSITIVE,
                strength=EvidenceStrength.STRONG,
                value_a=val_a,
                value_b=val_b,
                explanation=f"Same product type: {val_a}.",
            ))
        else:
            es.conflicts.append(Evidence(
                field="product_type",
                evidence_type=EvidenceType.CONFLICT,
                strength=EvidenceStrength.STRONG,
                severity=ConflictSeverity.CRITICAL,
                value_a=val_a,
                value_b=val_b,
                explanation=(
                    f"Product type conflict: '{val_a}' vs '{val_b}'."
                ),
            ))

    def _compare_brand(
        self, a: ProductIdentity, b: ProductIdentity, es: EvidenceSet
    ) -> None:
        """Compare brands."""
        val_a = (a.brand or "").lower().strip() or None
        val_b = (b.brand or "").lower().strip() or None

        if not val_a and not val_b:
            es.missing.append(Evidence(
                field="brand",
                evidence_type=EvidenceType.MISSING,
                strength=EvidenceStrength.MEDIUM,
                explanation="Neither identity has a detected brand.",
            ))
            return

        if not val_a or not val_b:
            es.missing.append(Evidence(
                field="brand",
                evidence_type=EvidenceType.MISSING,
                strength=EvidenceStrength.MEDIUM,
                value_a=a.brand,
                value_b=b.brand,
                explanation=(
                    f"Brand missing from one identity: "
                    f"'{a.brand or 'missing'}' vs '{b.brand or 'missing'}'."
                ),
            ))
            return

        if val_a == val_b:
            es.positive.append(Evidence(
                field="brand",
                evidence_type=EvidenceType.POSITIVE,
                strength=EvidenceStrength.STRONG,
                value_a=a.brand,
                value_b=b.brand,
                explanation=f"Same brand: {a.brand}.",
            ))
        else:
            es.conflicts.append(Evidence(
                field="brand",
                evidence_type=EvidenceType.CONFLICT,
                strength=EvidenceStrength.STRONG,
                severity=ConflictSeverity.STRONG,
                value_a=a.brand,
                value_b=b.brand,
                explanation=(
                    f"Brand conflict: '{a.brand}' vs '{b.brand}'."
                ),
            ))

    def _compare_model(
        self, a: ProductIdentity, b: ProductIdentity, es: EvidenceSet
    ) -> None:
        """Compare specific models."""
        val_a = (a.model or "").lower().strip() or None
        val_b = (b.model or "").lower().strip() or None

        if not val_a and not val_b:
            es.missing.append(Evidence(
                field="model",
                evidence_type=EvidenceType.MISSING,
                strength=EvidenceStrength.MEDIUM,
                explanation="Neither identity has a specific model.",
            ))
            return

        if not val_a or not val_b:
            es.missing.append(Evidence(
                field="model",
                evidence_type=EvidenceType.MISSING,
                strength=EvidenceStrength.MEDIUM,
                value_a=a.model,
                value_b=b.model,
                explanation=(
                    f"Model missing from one identity: "
                    f"'{a.model or 'missing'}' vs '{b.model or 'missing'}'."
                ),
            ))
            return

        if val_a == val_b:
            es.positive.append(Evidence(
                field="model",
                evidence_type=EvidenceType.POSITIVE,
                strength=EvidenceStrength.STRONG,
                value_a=a.model,
                value_b=b.model,
                explanation=f"Same model: {a.model}.",
            ))
        elif val_a in val_b or val_b in val_a:
            # One is a substring of the other — specificity difference
            es.negative.append(Evidence(
                field="model",
                evidence_type=EvidenceType.NEGATIVE,
                strength=EvidenceStrength.MEDIUM,
                severity=ConflictSeverity.MODERATE,
                value_a=a.model,
                value_b=b.model,
                explanation=(
                    f"Model specificity difference: "
                    f"'{a.model}' vs '{b.model}'."
                ),
            ))
        else:
            es.conflicts.append(Evidence(
                field="model",
                evidence_type=EvidenceType.CONFLICT,
                strength=EvidenceStrength.STRONG,
                severity=ConflictSeverity.STRONG,
                value_a=a.model,
                value_b=b.model,
                explanation=(
                    f"Model conflict: '{a.model}' vs '{b.model}'."
                ),
            ))

    def _compare_model_family(
        self, a: ProductIdentity, b: ProductIdentity, es: EvidenceSet
    ) -> None:
        """Compare model families."""
        val_a = (a.model_family or "").lower().strip() or None
        val_b = (b.model_family or "").lower().strip() or None

        if not val_a or not val_b:
            return  # Family is supplementary, don't report missing

        if val_a == val_b:
            es.positive.append(Evidence(
                field="model_family",
                evidence_type=EvidenceType.POSITIVE,
                strength=EvidenceStrength.MEDIUM,
                value_a=a.model_family,
                value_b=b.model_family,
                explanation=f"Same model family: {a.model_family}.",
            ))
        else:
            es.negative.append(Evidence(
                field="model_family",
                evidence_type=EvidenceType.NEGATIVE,
                strength=EvidenceStrength.MEDIUM,
                severity=ConflictSeverity.STRONG,
                value_a=a.model_family,
                value_b=b.model_family,
                explanation=(
                    f"Different model families: "
                    f"'{a.model_family}' vs '{b.model_family}'."
                ),
            ))

    def _compare_generation(
        self, a: ProductIdentity, b: ProductIdentity, es: EvidenceSet
    ) -> None:
        """Compare generation indicators."""
        val_a = (a.generation or "").lower().strip() or None
        val_b = (b.generation or "").lower().strip() or None

        if not val_a or not val_b:
            return  # Generation is supplementary

        if val_a == val_b:
            es.positive.append(Evidence(
                field="generation",
                evidence_type=EvidenceType.POSITIVE,
                strength=EvidenceStrength.MEDIUM,
                value_a=a.generation,
                value_b=b.generation,
                explanation=f"Same generation: {a.generation}.",
            ))
        else:
            es.conflicts.append(Evidence(
                field="generation",
                evidence_type=EvidenceType.CONFLICT,
                strength=EvidenceStrength.MEDIUM,
                severity=ConflictSeverity.MODERATE,
                value_a=a.generation,
                value_b=b.generation,
                explanation=(
                    f"Generation conflict: "
                    f"'{a.generation}' vs '{b.generation}'."
                ),
            ))

    def _compare_variant(
        self, a: ProductIdentity, b: ProductIdentity, es: EvidenceSet
    ) -> None:
        """Compare variants."""
        val_a = (a.variant or "").lower().strip() or None
        val_b = (b.variant or "").lower().strip() or None

        if not val_a or not val_b:
            return  # Variant is supplementary

        if val_a == val_b:
            es.positive.append(Evidence(
                field="variant",
                evidence_type=EvidenceType.POSITIVE,
                strength=EvidenceStrength.MEDIUM,
                value_a=a.variant,
                value_b=b.variant,
                explanation=f"Same variant: {a.variant}.",
            ))
        else:
            es.conflicts.append(Evidence(
                field="variant",
                evidence_type=EvidenceType.CONFLICT,
                strength=EvidenceStrength.MEDIUM,
                severity=ConflictSeverity.MODERATE,
                value_a=a.variant,
                value_b=b.variant,
                explanation=(
                    f"Variant conflict: '{a.variant}' vs '{b.variant}'."
                ),
            ))

    def _compare_condition(
        self, a: ProductIdentity, b: ProductIdentity, es: EvidenceSet
    ) -> None:
        """Compare product condition."""
        val_a = a.condition
        val_b = b.condition

        if not val_a or not val_b:
            return  # Condition often missing, don't penalize

        if val_a == val_b:
            es.positive.append(Evidence(
                field="condition",
                evidence_type=EvidenceType.POSITIVE,
                strength=EvidenceStrength.MEDIUM,
                value_a=val_a,
                value_b=val_b,
                explanation=f"Same condition: {val_a}.",
            ))
        else:
            es.negative.append(Evidence(
                field="condition",
                evidence_type=EvidenceType.NEGATIVE,
                strength=EvidenceStrength.WEAK,
                severity=ConflictSeverity.WEAK,
                value_a=val_a,
                value_b=val_b,
                explanation=(
                    f"Condition differs: '{val_a}' vs '{val_b}'."
                ),
            ))

    def _compare_accessory_context(
        self, a: ProductIdentity, b: ProductIdentity, es: EvidenceSet
    ) -> None:
        """
        Compare accessory vs device context.

        If one is an accessory and the other is a device, they cannot
        be the same product even if they share model names (the accessory
        is FOR the device, not IS the device).
        """
        if a.is_accessory != b.is_accessory:
            es.conflicts.append(Evidence(
                field="accessory_context",
                evidence_type=EvidenceType.CONFLICT,
                strength=EvidenceStrength.STRONG,
                severity=ConflictSeverity.CRITICAL,
                value_a=(
                    f"accessory (compatible: {a.compatible_models})"
                    if a.is_accessory
                    else f"device (model: {a.model})"
                ),
                value_b=(
                    f"accessory (compatible: {b.compatible_models})"
                    if b.is_accessory
                    else f"device (model: {b.model})"
                ),
                explanation=(
                    "One product is a device and the other is an accessory. "
                    "They are fundamentally different product types."
                ),
            ))

    def _compare_canonical_attributes(
        self, a: ProductIdentity, b: ProductIdentity, es: EvidenceSet
    ) -> None:
        """
        Compare canonical attributes using normalized values.

        Uses unit-normalized numeric values for fair comparison.
        Missing attributes are NOT treated as conflicts.
        Unknown normalized values are NOT treated as strong conflicts.
        """
        attrs_a = {
            attr.name: attr
            for attr in (a.canonical_attributes or [])
        }
        attrs_b = {
            attr.name: attr
            for attr in (b.canonical_attributes or [])
        }

        all_names = set(attrs_a.keys()) | set(attrs_b.keys())

        for name in sorted(all_names):
            attr_a = attrs_a.get(name)
            attr_b = attrs_b.get(name)

            if not attr_a and not attr_b:
                continue

            if not attr_a or not attr_b:
                es.missing.append(Evidence(
                    field=name,
                    evidence_type=EvidenceType.MISSING,
                    strength=EvidenceStrength.WEAK,
                    value_a=(
                        attr_a.normalized_value if attr_a else None
                    ),
                    value_b=(
                        attr_b.normalized_value if attr_b else None
                    ),
                    explanation=(
                        f"Attribute '{name}' present in one identity "
                        f"but missing from the other."
                    ),
                ))
                continue

            # Both have this attribute
            from .attributes import AttributeStatus

            # Check for unknown normalization
            if (
                attr_a.status == AttributeStatus.UNKNOWN
                or attr_b.status == AttributeStatus.UNKNOWN
            ):
                es.unknown.append(Evidence(
                    field=name,
                    evidence_type=EvidenceType.UNKNOWN,
                    strength=EvidenceStrength.WEAK,
                    value_a=attr_a.raw_value,
                    value_b=attr_b.raw_value,
                    explanation=(
                        f"Attribute '{name}' could not be fully normalized: "
                        f"'{attr_a.raw_value}' vs '{attr_b.raw_value}'."
                    ),
                ))
                continue

            # Compare using numeric values if available (unit-aware)
            if (
                attr_a.numeric_value is not None
                and attr_b.numeric_value is not None
            ):
                self._compare_numeric_attribute(
                    name, attr_a, attr_b, es
                )
            elif attr_a.normalized_value and attr_b.normalized_value:
                # String comparison
                if attr_a.normalized_value == attr_b.normalized_value:
                    es.positive.append(Evidence(
                        field=name,
                        evidence_type=EvidenceType.POSITIVE,
                        strength=EvidenceStrength.MEDIUM,
                        value_a=attr_a.normalized_value,
                        value_b=attr_b.normalized_value,
                        explanation=(
                            f"Attribute '{name}' matches: "
                            f"{attr_a.normalized_value}."
                        ),
                    ))
                else:
                    severity = self._attribute_conflict_severity(name)
                    es.conflicts.append(Evidence(
                        field=name,
                        evidence_type=EvidenceType.CONFLICT,
                        strength=EvidenceStrength.MEDIUM,
                        severity=severity,
                        value_a=attr_a.normalized_value,
                        value_b=attr_b.normalized_value,
                        explanation=(
                            f"Attribute '{name}' differs: "
                            f"'{attr_a.normalized_value}' vs "
                            f"'{attr_b.normalized_value}'."
                        ),
                    ))

    def _compare_numeric_attribute(
        self, name, attr_a, attr_b, es: EvidenceSet
    ) -> None:
        """Compare numeric attributes with unit awareness."""
        val_a = attr_a.numeric_value
        val_b = attr_b.numeric_value

        # Check for range overlap
        if attr_a.min_value is not None and attr_a.max_value is not None:
            if attr_a.min_value <= val_b <= attr_a.max_value:
                es.positive.append(Evidence(
                    field=name,
                    evidence_type=EvidenceType.POSITIVE,
                    strength=EvidenceStrength.MEDIUM,
                    value_a=attr_a.raw_value,
                    value_b=attr_b.raw_value,
                    explanation=(
                        f"'{name}': {val_b} falls within range "
                        f"{attr_a.min_value}-{attr_a.max_value}."
                    ),
                ))
                return

        # Exact or near-exact match (within 0.1% tolerance for float)
        if val_a == val_b or (
            val_a != 0
            and abs(val_a - val_b) / abs(val_a) < 0.001
        ):
            es.positive.append(Evidence(
                field=name,
                evidence_type=EvidenceType.POSITIVE,
                strength=EvidenceStrength.STRONG,
                value_a=attr_a.raw_value,
                value_b=attr_b.raw_value,
                explanation=(
                    f"Attribute '{name}' matches: "
                    f"{attr_a.raw_value} ≈ {attr_b.raw_value} "
                    f"(normalized: {val_a} {attr_a.unit or ''})."
                ),
            ))
        else:
            severity = self._attribute_conflict_severity(name)
            es.conflicts.append(Evidence(
                field=name,
                evidence_type=EvidenceType.CONFLICT,
                strength=EvidenceStrength.MEDIUM,
                severity=severity,
                value_a=attr_a.raw_value,
                value_b=attr_b.raw_value,
                explanation=(
                    f"Attribute '{name}' differs: "
                    f"{attr_a.raw_value} ({val_a} {attr_a.unit or ''}) "
                    f"vs {attr_b.raw_value} ({val_b} {attr_b.unit or ''})."
                ),
            ))

    def _attribute_conflict_severity(self, name: str) -> ConflictSeverity:
        """Determine conflict severity based on attribute name."""
        # Identity-critical attributes
        if name in ("storage", "memory"):
            return ConflictSeverity.STRONG
        # Variant-level attributes
        if name in ("color", "connectivity", "size"):
            return ConflictSeverity.MODERATE
        # Minor attributes
        return ConflictSeverity.WEAK