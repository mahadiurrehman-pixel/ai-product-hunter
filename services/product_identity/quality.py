"""
Data Quality & Confidence Layer + Data Quality Score (DQS).

Provides:
1. Field-level confidence assessment (FieldConfidence)
2. Product-level data quality reporting (DataQualityReport)
3. Deterministic Data Quality Score 0-100 (DataQualityScore)

CRITICAL DESIGN RULES:
- DQS = "how reliable is this extracted information?"
- DQS ≠ match score, sell probability, profit, policy compliance
- Missing data → completeness penalty, NOT consistency/validity conflict
- Unknown -> small quality limitation, NOT conflict
- Invalid -> validity penalty + severity cap
- Conflict -> consistency penalty (severity-aware)
- Same input -> same output (deterministic)
- No AI/LLM/ML — rule-based only

DQS Formula:
    DQS = completeness × 0.20
        + validity × 0.15
        + identity × 0.25
        + attributes × 0.15
        + source_quality × 0.10
        + consistency × 0.15

Score Caps:
    product_type unknown → DQS capped at 74 (cannot be EXCELLENT/GOOD)
    strong identity conflict → DQS capped at 59 (cannot be FAIR+)
    core field invalid → DQS capped at 59 (cannot be FAIR+)
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from utils.logger import get_logger

from .models import ProductIdentity, DataQuality
from .attributes import AttributeStatus, CanonicalAttribute

logger = get_logger(__name__)


# =============================================================================
# Confidence Levels
# =============================================================================

class ConfidenceLevel(str, Enum):
    """
    Deterministic confidence level for extracted information.

    HIGH:    Structured API field or exact configured match
    MEDIUM:  Clearly extracted from title via deterministic parser
    LOW:     Weak or ambiguous textual inference
    UNKNOWN: No usable evidence available
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"

    @property
    def score(self) -> float:
        """Numeric score for aggregation (0.0-1.0)."""
        scores = {
            ConfidenceLevel.HIGH: 0.9,
            ConfidenceLevel.MEDIUM: 0.6,
            ConfidenceLevel.LOW: 0.3,
            ConfidenceLevel.UNKNOWN: 0.0,
        }
        return scores[self]


# =============================================================================
# Quality Flags
# =============================================================================

class QualityFlag(str, Enum):
    MISSING_PRODUCT_TYPE = "MISSING_PRODUCT_TYPE"
    MISSING_BRAND = "MISSING_BRAND"
    MISSING_MODEL = "MISSING_MODEL"
    MISSING_CONDITION = "MISSING_CONDITION"
    MISSING_PRICE = "MISSING_PRICE"
    MISSING_IMAGE = "MISSING_IMAGE"
    MISSING_URL = "MISSING_URL"
    UNKNOWN_ATTRIBUTE = "UNKNOWN_ATTRIBUTE"
    CONFLICTING_ATTRIBUTE = "CONFLICTING_ATTRIBUTE"
    CONFLICTING_MODEL = "CONFLICTING_MODEL"
    CONFLICTING_BRAND = "CONFLICTING_BRAND"
    CONFLICTING_PRODUCT_TYPE = "CONFLICTING_PRODUCT_TYPE"
    ACCESSORY_DEVICE_MISMATCH = "ACCESSORY_DEVICE_MISMATCH"
    LOW_SOURCE_CONFIDENCE = "LOW_SOURCE_CONFIDENCE"
    INCOMPLETE_IDENTITY = "INCOMPLETE_IDENTITY"
    INVALID_PRICE = "INVALID_PRICE"
    UNKNOWN_PRODUCT_TYPE = "UNKNOWN_PRODUCT_TYPE"


# =============================================================================
# DQS Quality Levels
# =============================================================================

class DQSLevel(str, Enum):
    """Data Quality Score level."""
    EXCELLENT = "EXCELLENT"   # 90-100
    GOOD = "GOOD"             # 75-89
    FAIR = "FAIR"             # 60-74
    LOW = "LOW"               # 40-59
    VERY_LOW = "VERY_LOW"     # 0-39

    @classmethod
    def from_score(cls, score: float) -> "DQSLevel":
        if score >= 90:
            return cls.EXCELLENT
        elif score >= 75:
            return cls.GOOD
        elif score >= 60:
            return cls.FAIR
        elif score >= 40:
            return cls.LOW
        else:
            return cls.VERY_LOW


# =============================================================================
# Field Confidence
# =============================================================================

@dataclass
class FieldConfidence:
    field: str
    confidence: ConfidenceLevel
    source: str = "unknown"
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "field": self.field,
            "confidence": self.confidence.value,
            "score": self.confidence.score,
            "source": self.source,
            "reason": self.reason,
        }


# =============================================================================
# Data Quality Score (DQS)
# =============================================================================

@dataclass
class DataQualityScore:
    """
    Deterministic Data Quality Score (0-100).

    Answers: "How complete, consistent, valid, and trustworthy is
    the product information currently available to REHU?"
    """

    overall_score: float = 0.0
    completeness_score: float = 0.0
    validity_score: float = 0.0
    identity_score: float = 0.0
    attribute_score: float = 0.0
    source_score: float = 0.0
    consistency_score: float = 0.0
    quality_level: str = "VERY_LOW"
    strengths: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    explanation: str = ""
    caps_applied: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "overall_score": round(self.overall_score, 1),
            "completeness_score": round(self.completeness_score, 1),
            "validity_score": round(self.validity_score, 1),
            "identity_score": round(self.identity_score, 1),
            "attribute_score": round(self.attribute_score, 1),
            "source_score": round(self.source_score, 1),
            "consistency_score": round(self.consistency_score, 1),
            "quality_level": self.quality_level,
            "strengths": self.strengths,
            "limitations": self.limitations,
            "flags": self.flags,
            "explanation": self.explanation,
            "caps_applied": self.caps_applied,
        }


# =============================================================================
# Data Quality Report (Legacy compatibility)
# =============================================================================

@dataclass
class DataQualityReport:
    completeness: float = 0.0
    consistency: float = 0.0
    source_quality: float = 0.0
    field_confidences: List[FieldConfidence] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)
    overall_quality: str = "LOW"
    explanation: str = ""

    @property
    def has_critical_issues(self) -> bool:
        critical = {
            QualityFlag.MISSING_PRODUCT_TYPE.value,
            QualityFlag.CONFLICTING_PRODUCT_TYPE.value,
            QualityFlag.ACCESSORY_DEVICE_MISMATCH.value,
        }
        return bool(set(self.flags) & critical)

    @property
    def conflict_flags(self) -> List[str]:
        return [f for f in self.flags if "CONFLICT" in f]

    @property
    def missing_flags(self) -> List[str]:
        return [f for f in self.flags if "MISSING" in f]

    def to_dict(self) -> dict:
        return {
            "completeness": round(self.completeness, 2),
            "consistency": round(self.consistency, 2),
            "source_quality": round(self.source_quality, 2),
            "field_confidences": [fc.to_dict() for fc in self.field_confidences],
            "flags": self.flags,
            "overall_quality": self.overall_quality,
            "explanation": self.explanation,
            "has_critical_issues": self.has_critical_issues,
            "conflict_count": len(self.conflict_flags),
            "missing_count": len(self.missing_flags),
        }


# =============================================================================
# Context-Aware Completeness Weights
# =============================================================================

COMPLETENESS_FIELDS_BY_ROLE: Dict[str, Dict[str, tuple]] = {
    "device": {
        "product_type": (0.20, "required"),
        "brand": (0.15, "important"),
        "model": (0.20, "required"),
        "condition": (0.10, "important"),
        "attributes": (0.15, "important"),
        "keywords": (0.10, "optional"),
        "price": (0.10, "important"),
    },
    "accessory": {
        "product_type": (0.20, "required"),
        "brand": (0.05, "optional"),
        "model": (0.05, "optional"),
        "compatible_models": (0.20, "required"),
        "condition": (0.10, "important"),
        "attributes": (0.15, "important"),
        "keywords": (0.10, "optional"),
        "price": (0.10, "important"),
    },
    "replacement_part": {
        "product_type": (0.20, "required"),
        "brand": (0.05, "optional"),
        "model": (0.10, "important"),
        "compatible_models": (0.20, "required"),
        "condition": (0.05, "optional"),
        "attributes": (0.15, "important"),
        "keywords": (0.10, "optional"),
        "price": (0.10, "important"),
    },
    "consumable": {
        "product_type": (0.20, "required"),
        "brand": (0.10, "important"),
        "model": (0.05, "optional"),
        "compatible_models": (0.15, "important"),
        "condition": (0.05, "optional"),
        "attributes": (0.15, "important"),
        "keywords": (0.10, "optional"),
        "price": (0.10, "important"),
    },
    "component": {
        "product_type": (0.20, "required"),
        "brand": (0.10, "important"),
        "model": (0.10, "important"),
        "compatible_models": (0.10, "important"),
        "condition": (0.05, "optional"),
        "attributes": (0.15, "important"),
        "keywords": (0.10, "optional"),
        "price": (0.10, "important"),
    },
    "bundle": {
        "product_type": (0.20, "required"),
        "brand": (0.10, "important"),
        "model": (0.05, "optional"),
        "condition": (0.10, "important"),
        "attributes": (0.15, "important"),
        "keywords": (0.15, "important"),
        "price": (0.10, "important"),
    },
    "kit": {
        "product_type": (0.20, "required"),
        "brand": (0.10, "important"),
        "model": (0.05, "optional"),
        "condition": (0.10, "important"),
        "attributes": (0.15, "important"),
        "keywords": (0.15, "important"),
        "price": (0.10, "important"),
    },
    "unknown": {
        "product_type": (0.20, "required"),
        "brand": (0.10, "important"),
        "model": (0.10, "important"),
        "condition": (0.10, "important"),
        "attributes": (0.15, "important"),
        "keywords": (0.15, "important"),
        "price": (0.10, "important"),
    },
}

DQS_WEIGHTS = {
    "completeness": 0.20,
    "validity": 0.15,
    "identity": 0.25,
    "attributes": 0.15,
    "source_quality": 0.10,
    "consistency": 0.15,
}

SOURCE_QUALITY_SCORES: Dict[str, float] = {
    "structured_api": 0.95,
    "api": 0.90,
    "title": 0.70,
    "query": 0.60,
    "description": 0.50,
    "normalized_attribute": 0.70,
    "model_extractor": 0.75,
    "variant_extractor": 0.70,
    "compatibility_parser": 0.65,
    "unknown": 0.30,
}


# =============================================================================
# Data Quality Analyzer
# =============================================================================

class DataQualityAnalyzer:
    """
    Analyzes data quality and confidence for a ProductIdentity.
    """

    def analyze(
        self,
        identity: ProductIdentity,
        evidence_set=None,
    ) -> DataQualityReport:
        """Existing legacy analysis method."""
        field_confidences = self._assess_field_confidences(identity)
        completeness = self._assess_completeness(identity)
        consistency = self._assess_consistency(identity, evidence_set)
        source_quality = self._assess_source_quality(identity)
        flags = self._generate_flags(identity, field_confidences, evidence_set)
        overall = self._determine_overall_quality(
            completeness, consistency, source_quality, flags
        )
        explanation = self._generate_explanation(
            overall, completeness, consistency, source_quality,
            field_confidences, flags,
        )
        return DataQualityReport(
            completeness=completeness,
            consistency=consistency,
            source_quality=source_quality,
            field_confidences=field_confidences,
            flags=flags,
            overall_quality=overall,
            explanation=explanation,
        )

    def calculate_dqs(
        self,
        identity: ProductIdentity,
        evidence_set=None,
        listing_metadata: Optional[Dict] = None,
    ) -> DataQualityScore:
        """
        Calculate deterministic Data Quality Score (0-100).
        """
        completeness = self._dqs_completeness(identity, listing_metadata)
        validity = self._dqs_validity(identity, listing_metadata)
        identity_q = self._dqs_identity(identity)
        attr_q = self._dqs_attributes(identity)
        source_q = self._dqs_source(identity)
        consistency = self._dqs_consistency(identity, evidence_set)

        # Weighted combination
        raw_score = (
            completeness * DQS_WEIGHTS["completeness"]
            + validity * DQS_WEIGHTS["validity"]
            + identity_q * DQS_WEIGHTS["identity"]
            + attr_q * DQS_WEIGHTS["attributes"]
            + source_q * DQS_WEIGHTS["source_quality"]
            + consistency * DQS_WEIGHTS["consistency"]
        )

        caps = []
        score = raw_score

        if not identity.product_type or identity.product_type == "unknown":
            score = min(score, 74)
            caps.append("product_type unknown: DQS capped at 74 (FAIR max)")

        if evidence_set and evidence_set.has_critical_conflicts:
            score = min(score, 59)
            caps.append("critical identity conflict: DQS capped at 59 (LOW max)")

        if validity < 40:
            score = min(score, 59)
            caps.append("core field invalid: DQS capped at 59 (LOW max)")

        score = max(0.0, min(100.0, round(score, 1)))
        level = DQSLevel.from_score(score)

        strengths = self._dqs_strengths(
            completeness, validity, identity_q, attr_q, source_q, consistency
        )
        limitations = self._dqs_limitations(
            identity, completeness, validity, identity_q,
            attr_q, source_q, consistency, evidence_set,
        )

        flags = self._dqs_flags(identity, evidence_set, listing_metadata)
        explanation = self._dqs_explanation(
            score, level, strengths, limitations, caps
        )

        return DataQualityScore(
            overall_score=score,
            completeness_score=round(completeness, 1),
            validity_score=round(validity, 1),
            identity_score=round(identity_q, 1),
            attribute_score=round(attr_q, 1),
            source_score=round(source_q, 1),
            consistency_score=round(consistency, 1),
            quality_level=level.value,
            strengths=strengths,
            limitations=limitations,
            flags=flags,
            explanation=explanation,
            caps_applied=caps,
        )

    # =========================================================================
    # DQS Dimension Calculators
    # =========================================================================

    def _dqs_completeness(
        self,
        identity: ProductIdentity,
        listing_metadata: Optional[Dict] = None,
    ) -> float:
        role = identity.product_role or "unknown"
        field_weights = COMPLETENESS_FIELDS_BY_ROLE.get(
            role, COMPLETENESS_FIELDS_BY_ROLE["unknown"]
        )

        score = 0.0
        total_weight = 0.0

        for field_name, (weight, importance) in field_weights.items():
            total_weight += weight
            present = self._is_field_present(identity, field_name, listing_metadata)
            if present:
                score += weight * 100
            elif importance == "optional":
                score += weight * 60

        if total_weight == 0:
            return 50.0

        return min(100.0, score / total_weight)

    def _is_field_present(
        self,
        identity: ProductIdentity,
        field_name: str,
        listing_metadata: Optional[Dict] = None,
    ) -> bool:
        if field_name == "product_type":
            return bool(
                identity.product_type
                and identity.product_type != "unknown"
            )
        elif field_name == "brand":
            return bool(identity.brand)
        elif field_name == "model":
            return bool(identity.model)
        elif field_name == "condition":
            return bool(identity.condition)
        elif field_name == "attributes":
            return bool(
                identity.canonical_attributes
                and len(identity.canonical_attributes) > 0
            )
        elif field_name == "keywords":
            return bool(
                identity.keywords and len(identity.keywords) >= 2
            )
        elif field_name == "compatible_models":
            return bool(
                identity.compatible_models
                and len(identity.compatible_models) > 0
            )
        elif field_name == "price":
            if listing_metadata:
                price = listing_metadata.get("price") or listing_metadata.get("price_value")
                if price is not None:
                    try:
                        return float(price) > 0
                    except (ValueError, TypeError):
                        return False
            return bool(
                identity.get_canonical_attribute("price")
                or identity.get_canonical_attribute("wattage")
            )
        return False

    def _dqs_validity(
        self,
        identity: ProductIdentity,
        listing_metadata: Optional[Dict] = None,
    ) -> float:
        checks = 0
        passed = 0

        # Product type validity
        checks += 1
        if identity.product_type and identity.product_type != "unknown":
            passed += 1

        # Brand validity (if present, should be reasonable)
        if identity.brand:
            checks += 1
            if len(identity.brand.strip()) >= 2:
                passed += 1

        # Model validity (if present)
        if identity.model:
            checks += 1
            if len(identity.model) >= 2:
                passed += 1

        # Attribute validity
        for attr in (identity.canonical_attributes or []):
            checks += 1
            if attr.status == AttributeStatus.NORMALIZED:
                passed += 1
            elif attr.status == AttributeStatus.UNKNOWN:
                passed += 0.5

        # Metadata-driven structural validation (if provided)
        if listing_metadata:
            price = listing_metadata.get("price") or listing_metadata.get("price_value")
            if price is not None:
                checks += 1
                try:
                    if float(price) > 0:
                        passed += 1
                except (ValueError, TypeError):
                    pass

            currency = listing_metadata.get("currency") or listing_metadata.get("price_currency")
            if currency is not None:
                checks += 1
                if isinstance(currency, str) and len(currency) == 3 and currency.isalpha():
                    passed += 1

            listing_url = listing_metadata.get("listing_url") or listing_metadata.get("item_web_url") or listing_metadata.get("item_url")
            if listing_url is not None:
                checks += 1
                if isinstance(listing_url, str) and (listing_url.startswith("http://") or listing_url.startswith("https://")):
                    passed += 1

            image_url = listing_metadata.get("image_url") or listing_metadata.get("imageUrl")
            if image_url is not None:
                checks += 1
                if isinstance(image_url, str) and (image_url.startswith("http://") or image_url.startswith("https://")):
                    passed += 1

        if checks == 0:
            return 50.0

        return min(100.0, (passed / checks) * 100)

    def _dqs_identity(self, identity: ProductIdentity) -> float:
        base = identity.identity_confidence * 100
        if not identity.product_type or identity.product_type == "unknown":
            base = min(base, 40)
        if identity.product_role == "unknown":
            base = min(base, 50)
        if identity.is_accessory and identity.compatible_models:
            base = min(100, base + 10)
        if identity.is_accessory and identity.model:
            base = max(0, base - 20)
        return max(0.0, min(100.0, base))

    def _dqs_attributes(self, identity: ProductIdentity) -> float:
        attrs = identity.canonical_attributes or []
        if not attrs:
            return 30.0

        quality_scores = []
        for attr in attrs:
            if attr.status == AttributeStatus.NORMALIZED:
                if attr.source == "api":
                    quality_scores.append(95)
                elif attr.numeric_value is not None and attr.unit:
                    quality_scores.append(90)
                else:
                    quality_scores.append(70)
            elif attr.status == AttributeStatus.UNKNOWN:
                quality_scores.append(30)
            elif attr.status == AttributeStatus.CONFLICT:
                quality_scores.append(20)

        if not quality_scores:
            return 30.0

        return min(100.0, sum(quality_scores) / len(quality_scores))

    def _dqs_source(self, identity: ProductIdentity) -> float:
        sources = []
        for attr in (identity.canonical_attributes or []):
            sources.append(SOURCE_QUALITY_SCORES.get(attr.source, 0.5) * 100)

        if identity.brand:
            sources.append(SOURCE_QUALITY_SCORES.get("title", 0.7) * 100)
        if identity.model:
            sources.append(SOURCE_QUALITY_SCORES.get("model_extractor", 0.75) * 100)
        if identity.product_type:
            sources.append(SOURCE_QUALITY_SCORES.get("title", 0.7) * 100)

        if not sources:
            return 30.0

        return min(100.0, sum(sources) / len(sources))

    def _dqs_consistency(
        self, identity: ProductIdentity, evidence_set=None
    ) -> float:
        if evidence_set is None:
            return self._basic_consistency(identity) * 100

        from .evidence import ConflictSeverity

        critical = sum(1 for e in evidence_set.conflicts if e.severity == ConflictSeverity.CRITICAL)
        strong = sum(1 for e in evidence_set.conflicts if e.severity == ConflictSeverity.STRONG)
        moderate = sum(1 for e in evidence_set.conflicts if e.severity == ConflictSeverity.MODERATE)
        weak = sum(1 for e in evidence_set.conflicts if e.severity == ConflictSeverity.WEAK)

        penalty = critical * 30 + strong * 15 + moderate * 5 + weak * 2
        return max(0.0, min(100.0, 100.0 - penalty))

    # =========================================================================
    # DQS Helpers
    # =========================================================================

    def _dqs_strengths(
        self, comp, val, ident, attr, src, cons
    ) -> List[str]:
        strengths = []
        if ident >= 80:
            strengths.append("Product identity extracted reliably.")
        if comp >= 80:
            strengths.append("Most identity fields populated.")
        if val >= 90:
            strengths.append("Data values are structurally valid.")
        if attr >= 80:
            strengths.append("Attributes normalized successfully.")
        if src >= 80:
            strengths.append("Data from reliable sources.")
        if cons >= 90:
            strengths.append("No major identity conflicts detected.")
        return strengths

    def _dqs_limitations(
        self, identity, comp, val, ident, attr, src, cons, evidence_set
    ) -> List[str]:
        limitations = []
        if not identity.product_type:
            limitations.append("Product type could not be determined.")
        if not identity.brand:
            limitations.append("Brand not detected.")
        if not identity.model and identity.product_role == "device":
            limitations.append("Model missing for device product.")
        if comp < 50:
            limitations.append("Significant information gaps.")
        if cons < 60:
            limitations.append("Identity conflicts detected.")
        if attr < 50:
            limitations.append("Attribute quality is low.")
        if evidence_set:
            unknown_count = len(evidence_set.unknown)
            if unknown_count > 0:
                limitations.append(f"{unknown_count} attribute(s) could not be normalized.")
        return limitations

    def _dqs_flags(
        self, identity: ProductIdentity, evidence_set=None, listing_metadata: Optional[Dict] = None
    ) -> List[str]:
        flags = []
        if not identity.product_type:
            flags.append(QualityFlag.MISSING_PRODUCT_TYPE.value)
        if not identity.brand:
            flags.append(QualityFlag.MISSING_BRAND.value)
        if not identity.model:
            flags.append(QualityFlag.MISSING_MODEL.value)
        if not identity.condition:
            flags.append(QualityFlag.MISSING_CONDITION.value)
        if not identity.product_type or identity.product_type == "unknown":
            flags.append(QualityFlag.UNKNOWN_PRODUCT_TYPE.value)
        for attr in (identity.canonical_attributes or []):
            if attr.status == AttributeStatus.UNKNOWN:
                flags.append(QualityFlag.UNKNOWN_ATTRIBUTE.value)
            elif attr.status == AttributeStatus.CONFLICT:
                flags.append(QualityFlag.CONFLICTING_ATTRIBUTE.value)
        if identity.is_accessory and identity.model:
            flags.append(QualityFlag.ACCESSORY_DEVICE_MISMATCH.value)

        if listing_metadata:
            price = listing_metadata.get("price") or listing_metadata.get("price_value")
            if price is not None:
                try:
                    if float(price) <= 0:
                        flags.append(QualityFlag.INVALID_PRICE.value)
                except (ValueError, TypeError):
                    flags.append(QualityFlag.INVALID_PRICE.value)

        if evidence_set:
            from .evidence import ConflictSeverity
            for e in evidence_set.conflicts:
                if e.field == "brand" and e.severity in (
                    ConflictSeverity.CRITICAL, ConflictSeverity.STRONG
                ):
                    if QualityFlag.CONFLICTING_BRAND.value not in flags:
                        flags.append(QualityFlag.CONFLICTING_BRAND.value)
                elif e.field == "model" and e.severity in (
                    ConflictSeverity.CRITICAL, ConflictSeverity.STRONG
                ):
                    if QualityFlag.CONFLICTING_MODEL.value not in flags:
                        flags.append(QualityFlag.CONFLICTING_MODEL.value)
        return flags

    def _dqs_explanation(
        self, score, level, strengths, limitations, caps
    ) -> str:
        parts = [f"DATA QUALITY: {score}/100 — {level.value}"]
        if strengths:
            parts.append("Strengths: " + "; ".join(strengths[:3]) + ".")
        if limitations:
            parts.append("Limitations: " + "; ".join(limitations[:3]) + ".")
        if caps:
            parts.append("Caps: " + "; ".join(caps) + ".")
        return " ".join(parts)

    # =========================================================================
    # Existing helpers (preserved)
    # =========================================================================

    def _assess_field_confidences(
        self, identity: ProductIdentity
    ) -> List[FieldConfidence]:
        confidences = []
        if identity.product_type:
            confidences.append(FieldConfidence(
                field="product_type", confidence=ConfidenceLevel.HIGH,
                source="product_type_detector",
                reason=f"Product type '{identity.product_type}' identified.",
            ))
        else:
            confidences.append(FieldConfidence(
                field="product_type", confidence=ConfidenceLevel.UNKNOWN,
                source="none", reason="No product type determined.",
            ))
        if identity.brand:
            confidences.append(FieldConfidence(
                field="brand", confidence=ConfidenceLevel.HIGH,
                source="brand_detector",
                reason=f"Brand '{identity.brand}' matched.",
            ))
        else:
            confidences.append(FieldConfidence(
                field="brand", confidence=ConfidenceLevel.UNKNOWN,
                source="none", reason="No brand detected.",
            ))
        if identity.model:
            confidences.append(FieldConfidence(
                field="model", confidence=ConfidenceLevel.HIGH,
                source="model_extractor",
                reason=f"Model '{identity.model}' extracted.",
            ))
        else:
            confidences.append(FieldConfidence(
                field="model", confidence=ConfidenceLevel.UNKNOWN,
                source="none", reason="No model detected.",
            ))
        if identity.variant:
            confidences.append(FieldConfidence(
                field="variant", confidence=ConfidenceLevel.MEDIUM,
                source="variant_extractor",
                reason=f"Variant '{identity.variant}' extracted.",
            ))
        if identity.condition:
            confidences.append(FieldConfidence(
                field="condition", confidence=ConfidenceLevel.MEDIUM,
                source="title",
                reason=f"Condition '{identity.condition}' extracted.",
            ))
        for attr in (identity.canonical_attributes or []):
            confidences.append(self._attribute_confidence(attr))
        if identity.keywords and len(identity.keywords) >= 3:
            confidences.append(FieldConfidence(
                field="keywords", confidence=ConfidenceLevel.MEDIUM,
                source="title",
                reason=f"{len(identity.keywords)} keywords extracted.",
            ))
        return confidences

    def _attribute_confidence(
        self, attr: CanonicalAttribute
    ) -> FieldConfidence:
        if attr.status == AttributeStatus.CONFLICT:
            return FieldConfidence(
                field=attr.name, confidence=ConfidenceLevel.LOW,
                source=attr.source,
                reason=f"Conflicting values for '{attr.name}'.",
            )
        if attr.status == AttributeStatus.UNKNOWN:
            return FieldConfidence(
                field=attr.name, confidence=ConfidenceLevel.LOW,
                source=attr.source,
                reason=f"'{attr.name}' could not be normalized.",
            )
        if attr.source == "api":
            return FieldConfidence(
                field=attr.name, confidence=ConfidenceLevel.HIGH,
                source="structured_api",
                reason=f"'{attr.name}' from structured API.",
            )
        if attr.numeric_value is not None and attr.unit:
            return FieldConfidence(
                field=attr.name, confidence=ConfidenceLevel.HIGH,
                source=attr.source,
                reason=f"'{attr.name}' normalized: {attr.numeric_value} {attr.unit}.",
            )
        return FieldConfidence(
            field=attr.name, confidence=ConfidenceLevel.MEDIUM,
            source=attr.source,
            reason=f"'{attr.name}' from title.",
        )

    def _assess_completeness(self, identity: ProductIdentity) -> float:
        score = 0.0
        checks = {
            "product_type": bool(identity.product_type),
            "brand": bool(identity.brand),
            "model": bool(identity.model),
            "condition": bool(identity.condition),
            "attributes": bool(
                identity.canonical_attributes
                and len(identity.canonical_attributes) > 0
            ),
            "keywords": bool(
                identity.keywords and len(identity.keywords) >= 2
            ),
        }
        weights = {
            "product_type": 0.25, "brand": 0.20, "model": 0.20,
            "condition": 0.10, "attributes": 0.15, "keywords": 0.10,
        }
        for field_name, present in checks.items():
            if present:
                score += weights.get(field_name, 0.0)
        return min(1.0, round(score, 2))

    def _assess_consistency(
        self, identity: ProductIdentity, evidence_set=None
    ) -> float:
        if evidence_set is None:
            return self._basic_consistency(identity)
        from .evidence import ConflictSeverity
        critical = sum(1 for e in evidence_set.conflicts if e.severity == ConflictSeverity.CRITICAL)
        strong = sum(1 for e in evidence_set.conflicts if e.severity == ConflictSeverity.STRONG)
        moderate = sum(1 for e in evidence_set.conflicts if e.severity == ConflictSeverity.MODERATE)
        weak = sum(1 for e in evidence_set.conflicts if e.severity == ConflictSeverity.WEAK)
        penalty = critical * 0.30 + strong * 0.15 + moderate * 0.05 + weak * 0.02
        return max(0.0, round(1.0 - penalty, 2))

    def _basic_consistency(self, identity: ProductIdentity) -> float:
        penalty = 0.0
        for attr in (identity.canonical_attributes or []):
            if attr.status == AttributeStatus.CONFLICT:
                penalty += 0.10
        if identity.is_accessory and identity.model:
            penalty += 0.20
        return max(0.0, round(1.0 - penalty, 2))

    def _assess_source_quality(self, identity: ProductIdentity) -> float:
        sources = []
        for attr in (identity.canonical_attributes or []):
            sources.append(SOURCE_QUALITY_SCORES.get(attr.source, 0.5))
        if identity.brand:
            sources.append(SOURCE_QUALITY_SCORES.get("title", 0.7))
        if identity.model:
            sources.append(SOURCE_QUALITY_SCORES.get("model_extractor", 0.75))
        if identity.product_type:
            sources.append(SOURCE_QUALITY_SCORES.get("title", 0.7))
        if not sources:
            return 0.3
        return round(min(1.0, sum(sources) / len(sources)), 2)

    def _generate_flags(
        self, identity, field_confidences, evidence_set
    ) -> List[str]:
        flags = []
        if not identity.product_type:
            flags.append(QualityFlag.MISSING_PRODUCT_TYPE.value)
        if not identity.brand:
            flags.append(QualityFlag.MISSING_BRAND.value)
        if not identity.model:
            flags.append(QualityFlag.MISSING_MODEL.value)
        if not identity.condition:
            flags.append(QualityFlag.MISSING_CONDITION.value)
        for attr in (identity.canonical_attributes or []):
            if attr.status == AttributeStatus.UNKNOWN:
                flags.append(QualityFlag.UNKNOWN_ATTRIBUTE.value)
            elif attr.status == AttributeStatus.CONFLICT:
                flags.append(QualityFlag.CONFLICTING_ATTRIBUTE.value)
        if identity.is_accessory and identity.model:
            flags.append(QualityFlag.ACCESSORY_DEVICE_MISMATCH.value)
        if evidence_set:
            from .evidence import ConflictSeverity
            for e in evidence_set.conflicts:
                if e.field == "model" and e.severity in (
                    ConflictSeverity.CRITICAL, ConflictSeverity.STRONG
                ):
                    if QualityFlag.CONFLICTING_MODEL.value not in flags:
                        flags.append(QualityFlag.CONFLICTING_MODEL.value)
                elif e.field == "brand" and e.severity in (
                    ConflictSeverity.CRITICAL, ConflictSeverity.STRONG
                ):
                    if QualityFlag.CONFLICTING_BRAND.value not in flags:
                        flags.append(QualityFlag.CONFLICTING_BRAND.value)
        if len(flags) >= 3:
            flags.append(QualityFlag.INCOMPLETE_IDENTITY.value)
        low_sources = [
            fc for fc in field_confidences
            if fc.confidence == ConfidenceLevel.LOW
        ]
        if len(low_sources) >= 2:
            flags.append(QualityFlag.LOW_SOURCE_CONFIDENCE.value)
        return flags

    def _determine_overall_quality(
        self, completeness, consistency, source_quality, flags
    ) -> str:
        has_critical = any(
            f in (
                QualityFlag.MISSING_PRODUCT_TYPE.value,
                QualityFlag.CONFLICTING_PRODUCT_TYPE.value,
                QualityFlag.ACCESSORY_DEVICE_MISMATCH.value,
            )
            for f in flags
        )
        if has_critical:
            return "LOW"
        if completeness >= 0.6 and consistency >= 0.8 and source_quality >= 0.7:
            return "HIGH"
        if completeness >= 0.4 and consistency >= 0.5 and source_quality >= 0.5:
            return "MEDIUM"
        return "LOW"

    def _generate_explanation(
        self, overall, completeness, consistency, source_quality,
        field_confidences, flags,
    ) -> str:
        parts = [f"DATA QUALITY: {overall}"]
        if completeness >= 0.7:
            parts.append("Most identity fields populated.")
        elif completeness >= 0.4:
            parts.append("Some identity fields missing.")
        else:
            parts.append("Many identity fields missing.")
        if consistency >= 0.9:
            parts.append("No major identity conflicts.")
        elif consistency >= 0.6:
            parts.append("Minor inconsistencies.")
        else:
            parts.append("Significant conflicts.")
        if source_quality >= 0.8:
            parts.append("Reliable sources.")
        elif source_quality >= 0.5:
            parts.append("Title-extracted data.")
        else:
            parts.append("Limited sources.")
        return " ".join(parts)