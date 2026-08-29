"""
eBay policy risk checking service.

⚠️ PATTERN-BASED HEURISTIC SCREENING TOOL.
NOT verified against current live eBay policy pages.
NOT legal or compliance advice.
Always verify flagged issues against current official eBay policies.
"""
from .checker import PolicyChecker
from .models import (
    DetectionConfidence,
    EvidenceStrength,
    PolicyAssessment,
    PolicyFinding,
    PolicyRiskCategory,
    PolicyRiskLevel,
    PolicySource,
    PolicyVerificationStatus,
)

__all__ = [
    "PolicyChecker",
    "PolicyAssessment",
    "PolicyFinding",
    "PolicyRiskLevel",
    "PolicyRiskCategory",
    "PolicySource",
    "PolicyVerificationStatus",
    "EvidenceStrength",
    "DetectionConfidence",
]