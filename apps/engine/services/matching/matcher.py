"""
Product Matching Engine (Hardened + Pre-Phase 6.1-6.6).

Pipeline:
1. Candidate filtering (lightweight pre-filter)
2. Build identities
3. Hard rejection (type/brand/accessory)
4. Text similarity (Jaccard + boosts)
5. Attribute similarity (unit-aware)
6. Compatibility similarity
7. Identifier similarity
8. Condition similarity
9. Variant similarity
10. Quantity similarity
11. Identity evidence (ConflictDetector)
12. Adjust evidence based on compatibility
13. Category-aware weighting
14. Combine with explanation + provenance
15. Confidence from data quality + evidence
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from utils.logger import get_logger
from services.product_identity import (
    ProductIdentity,
    ProductIdentityBuilder,
    ConflictDetector,
    EvidenceSet,
    ConflictSeverity,
    DataQualityAnalyzer,
)
from services.product_identity.taxonomy import TaxonomyEngine
from services.aliexpress.models import AliExpressProduct
from .similarity import (
    TextSimilarity,
    AttributeSimilarity,
    CompatibilitySimilarity,
    IdentifierSimilarity,
    ConditionSimilarity,
    VariantSimilarity,
    QuantitySimilarity,
)
from .candidate_filter import CandidateFilter, CandidateStatus

logger = get_logger(__name__)
_taxonomy = TaxonomyEngine()
_dqs_analyzer = DataQualityAnalyzer()

MATCHER_VERSION = "1.1.0"
TAXONOMY_VERSION = "1.0.0"


@dataclass
class ProductMatchResult:
    """Result of matching one eBay listing to one AliExpress product."""

    ebay_item_id: str
    ali_product_id: str
    match_score: float = 0.0
    confidence: float = 0.0
    match_type: str = "unlikely"

    # Similarity breakdowns
    text_similarity: float = 0.0
    attribute_similarity: float = 0.0
    compatibility_similarity: float = 0.5
    identifier_similarity: float = 0.5
    condition_similarity: float = 0.5
    variant_similarity: float = 0.5
    quantity_similarity: float = 0.5

    # Explanation
    matching_reasons: List[str] = field(default_factory=list)
    differing_attributes: List[str] = field(default_factory=list)
    positive_evidence: List[str] = field(default_factory=list)
    negative_evidence: List[str] = field(default_factory=list)
    penalties: List[str] = field(default_factory=list)
    score_contributions: Dict[str, float] = field(default_factory=dict)

    # Provenance (Pre-Phase 6.6)
    matcher_version: str = MATCHER_VERSION
    taxonomy_version: str = TAXONOMY_VERSION
    matched_at: Optional[str] = None

    # Evidence & identities
    identity_evidence: Optional[EvidenceSet] = None
    ebay_identity: Optional[ProductIdentity] = None
    ali_identity: Optional[ProductIdentity] = None

    def to_dict(self) -> dict:
        return {
            "ebay_item_id": self.ebay_item_id,
            "ali_product_id": self.ali_product_id,
            "match_score": round(self.match_score, 4),
            "confidence": round(self.confidence, 4),
            "match_type": self.match_type,
            "similarities": {
                "text": round(self.text_similarity, 4),
                "attribute": round(self.attribute_similarity, 4),
                "compatibility": round(self.compatibility_similarity, 4),
                "identifier": round(self.identifier_similarity, 4),
                "condition": round(self.condition_similarity, 4),
                "variant": round(self.variant_similarity, 4),
                "quantity": round(self.quantity_similarity, 4),
            },
            "positive_evidence": self.positive_evidence,
            "negative_evidence": self.negative_evidence,
            "penalties": self.penalties,
            "score_contributions": {
                k: round(v, 4)
                for k, v in self.score_contributions.items()
            },
            "matching_reasons": self.matching_reasons,
            "differing_attributes": self.differing_attributes,
            "provenance": {
                "matcher_version": self.matcher_version,
                "taxonomy_version": self.taxonomy_version,
                "matched_at": self.matched_at,
            },
        }


class ProductMatcher:
    """Hardened product matcher with candidate filtering and provenance."""

    # Default weights (used when no category-specific config)
    # Must sum to exactly 1.00
    DEFAULT_WEIGHTS = {
        "text": 0.18,
        "attribute": 0.13,
        "compatibility": 0.13,
        "identifier": 0.10,
        "condition": 0.05,
        "variant": 0.10,
        "quantity": 0.07,
        "evidence": 0.24,
    }
    MATCH_THRESHOLDS = [
        (0.90, "exact"),
        (0.75, "very_similar"),
        (0.60, "similar"),
        (0.40, "possible"),
        (0.00, "unlikely"),
    ]

    def __init__(self, use_candidate_filter: bool = True):
        self._builder = ProductIdentityBuilder()
        self._detector = ConflictDetector()
        self._text_sim = TextSimilarity()
        self._attr_sim = AttributeSimilarity()
        self._compat_sim = CompatibilitySimilarity()
        self._id_sim = IdentifierSimilarity()
        self._cond_sim = ConditionSimilarity()
        self._var_sim = VariantSimilarity()
        self._qty_sim = QuantitySimilarity()
        self._candidate_filter = (
            CandidateFilter() if use_candidate_filter else None
        )

    def find_matches(
        self,
        ebay_listing: dict,
        aliexpress_products: List[AliExpressProduct],
        min_score: float = 0.60,
    ) -> List[ProductMatchResult]:
        if not ebay_listing or not aliexpress_products:
            return []

        ebay_identity = self._builder.from_ebay_listing(ebay_listing)

        # Build AliExpress identities
        ali_identities = [
            self._builder.from_aliexpress_product(p)
            for p in aliexpress_products
        ]

        # Phase 6.1: Candidate filtering
        if self._candidate_filter:
            eligible, filtered = self._candidate_filter.filter_candidates(
                ebay_identity, ali_identities
            )
            ali_identities = [c.ali_identity for c in eligible]
            logger.info(
                f"Candidate filter: {len(ali_identities)} eligible "
                f"from {len(aliexpress_products)} candidates"
            )

        results = []
        for ali_identity in ali_identities:
            match = self.match_pair(ebay_identity, ali_identity)
            if match.match_score >= min_score:
                results.append(match)

        results.sort(key=lambda m: m.match_score, reverse=True)
        return results

    def match_pair(
        self,
        ebay_identity: ProductIdentity,
        ali_identity: ProductIdentity,
    ) -> ProductMatchResult:
        ebay_id = (
            getattr(ebay_identity, "ebay_item_id", "")
            or ebay_identity.identity_key
        )
        ali_id = (
            getattr(ali_identity, "ali_product_id", "")
            or ali_identity.identity_key
        )
        matched_at = datetime.utcnow().isoformat()

        # Hard rejection
        rejection = self._check_hard_rejection(
            ebay_identity, ali_identity
        )
        if rejection:
            return ProductMatchResult(
                ebay_item_id=ebay_id,
                ali_product_id=ali_id,
                match_score=0.0,
                confidence=0.0,
                match_type="unlikely",
                negative_evidence=[rejection],
                matched_at=matched_at,
                ebay_identity=ebay_identity,
                ali_identity=ali_identity,
            )

        # Calculate all similarities
        text_sim, text_matches = self._text_sim.calculate(
            ebay_identity, ali_identity
        )
        attr_sim, attr_matches, attr_diffs = self._attr_sim.calculate(
            ebay_identity, ali_identity
        )
        compat_sim, compat_ev = self._compat_sim.calculate(
            ebay_identity, ali_identity
        )
        id_sim, id_ev = self._id_sim.calculate(
            ebay_identity, ali_identity
        )
        cond_sim, cond_ev = self._cond_sim.calculate(
            ebay_identity, ali_identity
        )
        var_sim, var_matches, var_diffs = self._var_sim.calculate(
            ebay_identity, ali_identity
        )
        qty_sim, qty_ev = self._qty_sim.calculate(
            ebay_identity, ali_identity
        )

        # Identity evidence
        evidence = self._detector.compare(
            ebay_identity, ali_identity
        )
        evidence_score = self._calc_evidence_score(evidence)

        # Adjust evidence based on compatibility
        if compat_sim < 0.3:
            evidence_score *= 0.5
        elif compat_sim < 0.5:
            evidence_score *= 0.75

        # Category-aware weights
        weights = self._get_category_weights(ebay_identity)

        # Combine
        contributions = {
            "text": text_sim * weights.get("text", 0.18),
            "attribute": attr_sim * weights.get("attribute", 0.13),
            "compatibility": compat_sim * weights.get("compatibility", 0.13),
            "identifier": id_sim * weights.get("identifier", 0.09),
            "condition": cond_sim * weights.get("condition", 0.05),
            "variant": var_sim * weights.get("variant", 0.09),
            "quantity": qty_sim * weights.get("quantity", 0.07),
            "evidence": evidence_score * weights.get("evidence", 0.22),
        }
        match_score = max(
            0.0, min(1.0, round(sum(contributions.values()), 4))
        )

        # Confidence
        dqs_ebay = _dqs_analyzer.calculate_dqs(ebay_identity)
        dqs_ali = _dqs_analyzer.calculate_dqs(ali_identity)
        confidence = min(
            ebay_identity.identity_confidence,
            ali_identity.identity_confidence,
            evidence_score,
            dqs_ebay.overall_score / 100.0,
            dqs_ali.overall_score / 100.0,
        )
        confidence = max(0.0, min(1.0, round(confidence, 4)))

        # Build explanation
        positive = list(text_matches[:3]) + attr_matches + var_matches
        positive += [
            e for e in compat_ev if "compatible" in e.lower()
        ]
        positive += [e for e in id_ev if "match" in e.lower()]
        positive += [e for e in cond_ev if "same" in e.lower()]
        positive += [
            e for e in qty_ev if "same" in e.lower()
        ]

        negative = list(attr_diffs) + list(var_diffs)
        negative += [
            e for e in compat_ev
            if "not" in e.lower() or "different" in e.lower()
        ]
        negative += [e for e in id_ev if "conflict" in e.lower()]
        negative += [
            e for e in cond_ev
            if "mismatch" in e.lower() or "differs" in e.lower()
        ]
        negative += [
            e for e in qty_ev if "mismatch" in e.lower()
        ]

        penalties = []
        if evidence_score < 0.5:
            penalties.append(
                f"Identity conflicts reduced evidence to "
                f"{evidence_score:.2f}"
            )
        if dqs_ebay.overall_score < 50 or dqs_ali.overall_score < 50:
            penalties.append("Low data quality reduced confidence")

        match_type = self._classify(match_score)

        return ProductMatchResult(
            ebay_item_id=ebay_id,
            ali_product_id=ali_id,
            match_score=match_score,
            confidence=confidence,
            match_type=match_type,
            text_similarity=text_sim,
            attribute_similarity=attr_sim,
            compatibility_similarity=compat_sim,
            identifier_similarity=id_sim,
            condition_similarity=cond_sim,
            variant_similarity=var_sim,
            quantity_similarity=qty_sim,
            matching_reasons=positive[:5],
            differing_attributes=negative[:5],
            positive_evidence=positive,
            negative_evidence=negative,
            penalties=penalties,
            score_contributions=contributions,
            matched_at=matched_at,
            identity_evidence=evidence,
            ebay_identity=ebay_identity,
            ali_identity=ali_identity,
        )

    def _check_hard_rejection(
        self,
        ebay: ProductIdentity,
        ali: ProductIdentity,
    ) -> Optional[str]:
        et = (ebay.product_type or "").lower()
        at = (ali.product_type or "").lower()

        if (
            et and at
            and et != "unknown" and at != "unknown"
            and et != at
        ):
            if ebay.is_accessory and ali.is_accessory:
                if et != at:
                    return (
                        f"Product type mismatch: "
                        f"'{ebay.product_type}' vs '{ali.product_type}'"
                    )
            elif ebay.is_accessory != ali.is_accessory:
                acc = ebay if ebay.is_accessory else ali
                dev = ali if ebay.is_accessory else ebay
                if not self._is_compatible(acc, dev):
                    return "Accessory vs device mismatch"
            else:
                return (
                    f"Product type mismatch: "
                    f"'{ebay.product_type}' vs '{ali.product_type}'"
                )

        eb = (ebay.brand or "").lower().strip()
        ab = (ali.brand or "").lower().strip()
        if eb and ab and eb != ab:
            return (
                f"Brand mismatch: '{ebay.brand}' vs '{ali.brand}'"
            )

        return None

    def _is_compatible(
        self, acc: ProductIdentity, dev: ProductIdentity
    ) -> bool:
        if acc.compatible_models and dev.model:
            dm = dev.model.lower()
            for c in acc.compatible_models:
                if dm in c.lower() or c.lower() in dm:
                    return True
        if acc.compatible_categories and dev.product_type:
            if dev.product_type in acc.compatible_categories:
                return True
        return False

    def _calc_evidence_score(self, evidence: EvidenceSet) -> float:
        score = 1.0
        for c in evidence.conflicts:
            if c.severity == ConflictSeverity.CRITICAL:
                score -= 0.40
            elif c.severity == ConflictSeverity.STRONG:
                score -= 0.25
            elif c.severity == ConflictSeverity.MODERATE:
                score -= 0.10
            elif c.severity == ConflictSeverity.WEAK:
                score -= 0.05
        return max(0.0, round(score, 4))

    def _get_category_weights(
        self, identity: ProductIdentity
    ) -> Dict[str, float]:
        pt = identity.product_type
        if not pt:
            return self.DEFAULT_WEIGHTS

        info = _taxonomy.get_type(pt)
        if not info:
            return self.DEFAULT_WEIGHTS

        critical = (
            info.critical_attributes
            if hasattr(info, "critical_attributes")
            else []
        )
        identifiers = (
            info.identifiers
            if hasattr(info, "identifiers")
            else []
        )

        weights = dict(self.DEFAULT_WEIGHTS)

        if identifiers and any(i in critical for i in identifiers):
            weights["identifier"] = 0.12
            weights["text"] = max(0.10, weights["text"] - 0.03)

        if "compatible_models" in critical:
            weights["compatibility"] = 0.18
            weights["text"] = max(0.10, weights["text"] - 0.05)

        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def _classify(self, score: float) -> str:
        for threshold, mt in self.MATCH_THRESHOLDS:
            if score >= threshold:
                return mt
        return "unlikely"