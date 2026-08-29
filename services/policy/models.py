"""
Data models for eBay policy risk checking.

DESIGN CONTRACT:
This module encodes a PATTERN-BASED heuristic risk-screening system.
It is not a compliance verification system. Every finding is a signal
that human review may be warranted — nothing more.

Two distinct concepts to keep separate:
1. Detection Confidence — how confident the pattern matcher is that
   its detection is correct.
2. Evidence Strength — how much the detected pattern actually implies
   a real policy issue.

DISCLAIMER: This checker is a decision-support tool. It never claims
that a listing is compliant, prohibited, or that a seller will be
suspended. Findings guide human review only.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class PolicyVerificationStatus(str, Enum):
    """How well a rule/source has been verified against official eBay policy."""

    HEURISTIC = "heuristic_pattern_matching"
    REQUIRES_MANUAL_VERIFICATION = "requires_manual_verification"
    VERIFIED_OFFICIAL_SOURCE = "verified_official_source"


class PolicyRiskLevel(str, Enum):
    """Risk severity classification."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    REVIEW_REQUIRED = "review_required"

    @property
    def badge(self) -> str:
        badges = {
            PolicyRiskLevel.LOW: "🟢 LOW RISK",
            PolicyRiskLevel.MEDIUM: "🟡 MEDIUM RISK",
            PolicyRiskLevel.HIGH: "🔴 HIGH RISK",
            PolicyRiskLevel.REVIEW_REQUIRED: "⚪ REVIEW REQUIRED",
        }
        return badges[self]

    @property
    def priority(self) -> int:
        """Numeric priority for aggregation (higher = more severe)."""
        priorities = {
            PolicyRiskLevel.LOW: 1,
            PolicyRiskLevel.REVIEW_REQUIRED: 2,
            PolicyRiskLevel.MEDIUM: 3,
            PolicyRiskLevel.HIGH: 4,
        }
        return priorities[self]


class EvidenceStrength(str, Enum):
    """Strength of evidence that a pattern implies a real policy issue."""

    CONFIRMED = "confirmed"
    LIKELY = "likely"
    POTENTIAL = "potential"
    INSUFFICIENT = "insufficient"


class DetectionConfidence(str, Enum):
    """Confidence that the pattern matcher correctly identified its target."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class PolicyRiskCategory(str, Enum):
    """Categories of eBay policy risk."""

    # Product-level
    PROHIBITED_ITEM = "prohibited_item"
    RESTRICTED_ITEM = "restricted_item"
    ELIGIBILITY_REQUIRED = "eligibility_required"
    PRODUCT_SAFETY = "product_safety"
    HAZARDOUS_MATERIAL = "hazardous_material"
    IP_AUTHENTICITY = "ip_authenticity"

    # Listing/fulfillment-level
    LISTING_ACCURACY = "listing_accuracy"
    SHIPPING = "shipping"
    DROPSHIPPING = "dropshipping"

    # Seller-level
    SELLER_BEHAVIOR = "seller_behavior"
    SELLER_PERFORMANCE = "seller_performance"


@dataclass(frozen=True)
class PolicySource:
    """
    Reference to an official eBay policy source.
    Supports both `url` and `source_url` naming.
    """

    name: str
    url: Optional[str] = None
    source_url: Optional[str] = None
    verification_status: PolicyVerificationStatus = (
        PolicyVerificationStatus.HEURISTIC
    )
    last_verified: Optional[str] = None
    policy_revision: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self):
        resolved_url = self.source_url or self.url
        object.__setattr__(self, "source_url", resolved_url)
        object.__setattr__(self, "url", resolved_url)

        if (
            self.verification_status
            == PolicyVerificationStatus.VERIFIED_OFFICIAL_SOURCE
        ):
            if not resolved_url or not self.last_verified:
                raise ValueError(
                    f"PolicySource '{self.name}' marked VERIFIED_OFFICIAL_SOURCE "
                    "but is missing source_url or last_verified."
                )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "url": self.url,
            "source_url": self.source_url,
            "verification_status": self.verification_status.value,
            "last_verified": self.last_verified,
            "policy_revision": self.policy_revision,
            "notes": self.notes,
        }


@dataclass
class PolicyFinding:
    """A single policy finding from one rule."""

    category: PolicyRiskCategory
    risk_level: PolicyRiskLevel
    reason: str
    evidence: str
    evidence_strength: EvidenceStrength
    action: str
    source: PolicySource
    rule_id: str
    detection_confidence: DetectionConfidence = DetectionConfidence.MEDIUM

    def to_dict(self) -> dict:
        return {
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "risk_badge": self.risk_level.badge,
            "reason": self.reason,
            "evidence": self.evidence,
            "evidence_strength": self.evidence_strength.value,
            "detection_confidence": self.detection_confidence.value,
            "action": self.action,
            "source": self.source.to_dict(),
            "rule_id": self.rule_id,
            "verification_status": self.source.verification_status.value,
        }


@dataclass
class PolicyAssessment:
    """Complete policy risk assessment for a listing."""

    marketplace: str
    item_id: Optional[str]
    title: Optional[str]

    findings: List[PolicyFinding] = field(default_factory=list)
    overall_risk: PolicyRiskLevel = PolicyRiskLevel.LOW
    policy_version: str = "mvp-baseline-2025"
    assessed_at: datetime = field(default_factory=datetime.utcnow)

    disclaimer: str = (
        "⚠️ POLICY RISK SCREENING ONLY: This tool uses pattern-based "
        "heuristics to identify potential eBay policy risks. It does NOT "
        "determine whether an activity violates current eBay policy, "
        "is not legal advice, not compliance advice, and is not a compliance guarantee. "
        "Rules are not verified against current live eBay policy pages unless explicitly "
        "marked 'verified_official_source'. Policies can change and may vary by "
        "marketplace. Always verify flagged issues against current official eBay policies "
        "before listing."
    )

    limitations: List[str] = field(
        default_factory=lambda: [
            "⚠️ Rules are pattern-based heuristics, not verified against live eBay policy pages",
            "⚠️ eBay policies change frequently — verify current rules",
            "⚠️ Absence of findings does not mean the listing is compliant",
            "⚠️ Findings are advisory only — human review required",
            "⚠️ Marketplace-specific rules may differ from encoded rules",
            "⚠️ Detection confidence and policy risk are distinct",
        ]
    )

    @property
    def findings_by_category(self) -> dict:
        result = {}
        for f in self.findings:
            cat = f.category.value
            result.setdefault(cat, []).append(f)
        return result

    @property
    def has_high_risk(self) -> bool:
        return any(f.risk_level == PolicyRiskLevel.HIGH for f in self.findings)

    @property
    def has_review_required(self) -> bool:
        return any(
            f.risk_level == PolicyRiskLevel.REVIEW_REQUIRED for f in self.findings
        )

    @property
    def high_risk_findings(self) -> List[PolicyFinding]:
        return [f for f in self.findings if f.risk_level == PolicyRiskLevel.HIGH]

    @property
    def unverified_findings_count(self) -> int:
        return sum(
            1
            for f in self.findings
            if f.source.verification_status
            != PolicyVerificationStatus.VERIFIED_OFFICIAL_SOURCE
        )

    def to_dict(self) -> dict:
        return {
            "overall_risk": self.overall_risk.value,
            "overall_risk_badge": self.overall_risk.badge,
            "marketplace": self.marketplace,
            "item_id": self.item_id,
            "title": self.title,
            "findings": [f.to_dict() for f in self.findings],
            "finding_count": len(self.findings),
            "high_risk_finding_count": len(self.high_risk_findings),
            "has_high_risk": self.has_high_risk,
            "has_review_required": self.has_review_required,
            "unverified_findings_count": self.unverified_findings_count,
            "policy_version": self.policy_version,
            "assessed_at": self.assessed_at.isoformat(),
            "disclaimer": self.disclaimer,
            "limitations": self.limitations,
        }