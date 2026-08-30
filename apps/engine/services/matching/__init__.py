"""Product Matching Engine (Hardened + Pre-Phase 6)."""
from .matcher import ProductMatcher, ProductMatchResult, MATCHER_VERSION
from .similarity import (
    TextSimilarity,
    AttributeSimilarity,
    CompatibilitySimilarity,
    IdentifierSimilarity,
    ConditionSimilarity,
    VariantSimilarity,
    QuantitySimilarity,
)
from .candidate_filter import CandidateFilter, CandidateResult, CandidateStatus
from .bundle_detector import BundleDetector, BundleInfo
from .repository import MatchRepository

__all__ = [
    "ProductMatcher",
    "ProductMatchResult",
    "MATCHER_VERSION",
    "TextSimilarity",
    "AttributeSimilarity",
    "CompatibilitySimilarity",
    "IdentifierSimilarity",
    "ConditionSimilarity",
    "VariantSimilarity",
    "QuantitySimilarity",
    "CandidateFilter",
    "CandidateResult",
    "CandidateStatus",
    "BundleDetector",
    "BundleInfo",
    "MatchRepository",
]