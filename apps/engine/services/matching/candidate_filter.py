"""
Candidate Filtering / Blocking Layer (Pre-Phase 6.1).

Lightweight pre-filter that prevents the detailed ProductMatcher from
comparing every eBay listing against every supplier product.

Rules:
- Missing information does NOT reject a candidate
- Unknown information does NOT reject a candidate
- Only strong incompatibilities filter candidates
- Conservative: never silently remove potentially valid matches
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple

from utils.logger import get_logger
from services.product_identity.models import ProductIdentity

logger = get_logger(__name__)


class CandidateStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    FILTERED = "FILTERED"


@dataclass
class CandidateResult:
    """Result of candidate filtering for one product pair."""

    status: CandidateStatus
    reasons: List[str] = field(default_factory=list)
    ebay_identity: Optional[ProductIdentity] = None
    ali_identity: Optional[ProductIdentity] = None

    @property
    def is_eligible(self) -> bool:
        return self.status == CandidateStatus.ELIGIBLE

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "reasons": self.reasons,
        }


class CandidateFilter:
    """
    Lightweight candidate pre-filter.

    Checks product type, brand, model family, and accessory/device
    boundaries before passing to the detailed ProductMatcher.

    Conservative by design: only filters on strong incompatibilities.
    """

    def filter_pair(
        self,
        ebay_identity: ProductIdentity,
        ali_identity: ProductIdentity,
    ) -> CandidateResult:
        """
        Check if an eBay-AliExpress pair should proceed to detailed matching.

        Returns CandidateResult with ELIGIBLE or FILTERED status.
        """
        reasons = []
        filtered = False

        # Check 1: Product type compatibility
        type_ok, type_reason = self._check_product_type(
            ebay_identity, ali_identity
        )
        if not type_ok:
            filtered = True
            reasons.append(f"✗ {type_reason}")
        else:
            reasons.append(f"✓ {type_reason}")

        # Check 2: Brand compatibility
        brand_ok, brand_reason = self._check_brand(
            ebay_identity, ali_identity
        )
        if not brand_ok:
            filtered = True
            reasons.append(f"✗ {brand_reason}")
        else:
            reasons.append(f"✓ {brand_reason}")

        # Check 3: Model family compatibility
        family_ok, family_reason = self._check_model_family(
            ebay_identity, ali_identity
        )
        if not family_ok:
            filtered = True
            reasons.append(f"✗ {family_reason}")
        else:
            reasons.append(f"✓ {family_reason}")

        # Check 4: Accessory/device boundary
        acc_ok, acc_reason = self._check_accessory_boundary(
            ebay_identity, ali_identity
        )
        if not acc_ok:
            filtered = True
            reasons.append(f"✗ {acc_reason}")
        else:
            reasons.append(f"✓ {acc_reason}")

        status = (
            CandidateStatus.FILTERED if filtered
            else CandidateStatus.ELIGIBLE
        )

        return CandidateResult(
            status=status,
            reasons=reasons,
            ebay_identity=ebay_identity,
            ali_identity=ali_identity,
        )

    def filter_candidates(
        self,
        ebay_identity: ProductIdentity,
        ali_identities: List[ProductIdentity],
    ) -> Tuple[List[CandidateResult], List[CandidateResult]]:
        """
        Filter a list of AliExpress candidates against one eBay identity.

        Returns:
            Tuple of (eligible_candidates, filtered_candidates)
        """
        eligible = []
        filtered = []

        for ali_id in ali_identities:
            result = self.filter_pair(ebay_identity, ali_id)
            if result.is_eligible:
                eligible.append(result)
            else:
                filtered.append(result)

        logger.info(
            f"Candidate filter: {len(eligible)} eligible, "
            f"{len(filtered)} filtered from {len(ali_identities)} total"
        )

        return eligible, filtered

    def _check_product_type(
        self,
        ebay: ProductIdentity,
        ali: ProductIdentity,
    ) -> Tuple[bool, str]:
        """Check product type compatibility."""
        et = (ebay.product_type or "").lower()
        at = (ali.product_type or "").lower()

        if not et or not at or et == "unknown" or at == "unknown":
            return True, "Product type unknown — not filtering"

        if et == at:
            return True, f"Product type compatible ({et})"

        # Both accessories of different subtypes — still eligible
        if ebay.is_accessory and ali.is_accessory:
            return True, (
                f"Both accessories ({et} vs {at}) — "
                "detailed matching will decide"
            )

        return False, f"Product type conflict: '{et}' vs '{at}'"

    def _check_brand(
        self,
        ebay: ProductIdentity,
        ali: ProductIdentity,
    ) -> Tuple[bool, str]:
        """Check brand compatibility."""
        eb = (ebay.brand or "").lower().strip()
        ab = (ali.brand or "").lower().strip()

        if not eb or not ab:
            return True, "Brand unknown — not filtering"

        if eb == ab:
            return True, f"Brand matched ({ebay.brand})"

        return False, f"Brand conflict: '{ebay.brand}' vs '{ali.brand}'"

    def _check_model_family(
        self,
        ebay: ProductIdentity,
        ali: ProductIdentity,
    ) -> Tuple[bool, str]:
        """Check model family compatibility."""
        ef = (ebay.model_family or "").lower().strip()
        af = (ali.model_family or "").lower().strip()

        if not ef or not af:
            return True, "Model family unknown — not filtering"

        if ef == af:
            return True, f"Model family compatible ({ebay.model_family})"

        return False, (
            f"Model family conflict: '{ebay.model_family}' "
            f"vs '{ali.model_family}'"
        )

    def _check_accessory_boundary(
        self,
        ebay: ProductIdentity,
        ali: ProductIdentity,
    ) -> Tuple[bool, str]:
        """Check accessory vs device boundary."""
        if ebay.is_accessory == ali.is_accessory:
            return True, "Accessory/device role compatible"

        # One is accessory, other is device
        # Check if the accessory is compatible with the device
        acc = ebay if ebay.is_accessory else ali
        dev = ali if ebay.is_accessory else ebay

        if self._is_compatible(acc, dev):
            return True, (
                "Accessory compatible with device — "
                "detailed matching will decide"
            )

        return False, "Accessory vs device mismatch"

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