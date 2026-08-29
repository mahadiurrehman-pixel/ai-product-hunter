"""
Evidence and Conflict Detection Models.

Provides structured representation of evidence about product identity
comparison — positive matches, negative conflicts, missing data, and
unknown/ambiguous information.

CRITICAL DESIGN RULES:
- Missing ≠ Conflict (no information is not negative evidence)
- Unknown ≠ Conflict (unresolvable values are uncertain, not conflicting)
- This module NEVER produces match scores or match probabilities
- Evidence is factual reporting, not a matching decision
- The Phase 5 matcher consumes evidence to MAKE decisions
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class EvidenceType(str, Enum):
    """Type of evidence about a product identity field."""

    POSITIVE = "positive"     # Both sides agree
    NEGATIVE = "negative"     # Both sides explicitly disagree
    MISSING = "missing"       # One or both sides lack this information
    UNKNOWN = "unknown"       # Information present but cannot be normalized
    CONFLICT = "conflict"     # Structured data explicitly conflicts


class EvidenceStrength(str, Enum):
    """
    How reliable/significant this piece of evidence is.

    STRONG:  From structured API field or explicit title extraction
    MEDIUM:  From title-derived normalization
    WEAK:    From ambiguous or indirect inference
    """

    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


class ConflictSeverity(str, Enum):
    """
    How severe a detected conflict is for product identity.

    CRITICAL:  Different product types or incompatible models
               (almost certainly different products)
    STRONG:    Different brands or explicit model conflicts
    MODERATE:  Different variants or significant attribute differences
    WEAK:      Minor attribute differences that may not matter
    """

    CRITICAL = "critical"
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"


@dataclass
class Evidence:
    """
    A single piece of evidence about a product identity comparison.

    Does NOT contain a match score or match decision.
    Only contains factual observations about one field.

    Fields:
        field: Which identity field this is about (brand, model, color, etc.)
        evidence_type: POSITIVE/NEGATIVE/MISSING/UNKNOWN/CONFLICT
        strength: How reliable this evidence is
        severity: For conflicts, how severe (None for non-conflicts)
        value_a: Value from identity A (or None if missing)
        value_b: Value from identity B (or None if missing)
        source: Where this evidence came from
        explanation: Human-readable description of the evidence
    """

    field: str
    evidence_type: EvidenceType
    strength: EvidenceStrength
    severity: Optional[ConflictSeverity] = None
    value_a: Optional[str] = None
    value_b: Optional[str] = None
    source: str = "identity_comparison"
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "evidence_type": self.evidence_type.value,
            "strength": self.strength.value,
            "severity": self.severity.value if self.severity else None,
            "value_a": self.value_a,
            "value_b": self.value_b,
            "source": self.source,
            "explanation": self.explanation,
        }


@dataclass
class EvidenceSet:
    """
    Collection of all evidence from comparing two product identities.

    Separates evidence by type for clear consumption by future components.

    Does NOT contain:
    - match_score
    - match_probability
    - match_decision
    - ProductMatchResult

    Those belong to Phase 5.
    """

    positive: List[Evidence] = field(default_factory=list)
    negative: List[Evidence] = field(default_factory=list)
    missing: List[Evidence] = field(default_factory=list)
    unknown: List[Evidence] = field(default_factory=list)
    conflicts: List[Evidence] = field(default_factory=list)

    @property
    def all_evidence(self) -> List[Evidence]:
        """All evidence items combined."""
        return (
            self.positive + self.negative + self.missing
            + self.unknown + self.conflicts
        )

    @property
    def has_critical_conflicts(self) -> bool:
        """Whether any CRITICAL severity conflict exists."""
        return any(
            e.severity == ConflictSeverity.CRITICAL
            for e in self.conflicts
        )

    @property
    def has_strong_conflicts(self) -> bool:
        """Whether any STRONG severity conflict exists."""
        return any(
            e.severity == ConflictSeverity.STRONG
            for e in self.conflicts
        )

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def positive_count(self) -> int:
        return len(self.positive)

    @property
    def missing_count(self) -> int:
        return len(self.missing)

    def to_dict(self) -> dict:
        return {
            "positive": [e.to_dict() for e in self.positive],
            "negative": [e.to_dict() for e in self.negative],
            "missing": [e.to_dict() for e in self.missing],
            "unknown": [e.to_dict() for e in self.unknown],
            "conflicts": [e.to_dict() for e in self.conflicts],
            "summary": {
                "positive_count": self.positive_count,
                "conflict_count": self.conflict_count,
                "missing_count": self.missing_count,
                "has_critical_conflicts": self.has_critical_conflicts,
                "has_strong_conflicts": self.has_strong_conflicts,
                "total_evidence": len(self.all_evidence),
            },
        }