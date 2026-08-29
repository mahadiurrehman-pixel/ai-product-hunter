"""
eBay policy risk checker.

Aggregation rules:
- HIGH findings are always visible; they cannot be silently downgraded
- Overall risk is the maximum priority of individual findings
- Empty findings → LOW
- Any HIGH finding → overall HIGH
- Any MEDIUM finding (no HIGH) → overall MEDIUM
- Any REVIEW_REQUIRED finding (no HIGH/MEDIUM) → REVIEW_REQUIRED
"""
from typing import List, Optional, Union

from services.ebay.marketplace import EbayMarketplace
from utils.logger import get_logger

from .models import (
    PolicyAssessment,
    PolicyFinding,
    PolicyRiskLevel,
)
from .rules import (
    POLICY_VERSION,
    PRODUCT_LEVEL_RULES,
    SELLER_LEVEL_RULES,
)

logger = get_logger(__name__)


class PolicyChecker:
    """Assesses eBay policy risk for listings."""

    def check(
        self,
        listing: dict,
        marketplace: Union[EbayMarketplace, str] = EbayMarketplace.US,
        supplier: Optional[dict] = None,
    ) -> PolicyAssessment:
        marketplace_id = self._resolve_marketplace(marketplace)

        if not listing or not isinstance(listing, dict):
            return self._empty_assessment(marketplace_id)

        findings: List[PolicyFinding] = []

        for rule in PRODUCT_LEVEL_RULES:
            try:
                finding = rule(listing, supplier, marketplace_id)
                if finding is not None:
                    findings.append(finding)
            except Exception as e:
                logger.warning(
                    f"Rule {rule.__name__} failed: {e}. Skipping."
                )
                continue

        overall = self._compute_overall_risk(findings)

        logger.info(
            f"Policy check for {listing.get('item_id', 'unknown')} on "
            f"{marketplace_id}: {overall.value} ({len(findings)} findings)"
        )

        return PolicyAssessment(
            marketplace=marketplace_id,
            item_id=listing.get("item_id"),
            title=listing.get("title"),
            findings=findings,
            overall_risk=overall,
            policy_version=POLICY_VERSION,
        )

    def check_seller(
        self,
        seller_data: dict,
        marketplace: Union[EbayMarketplace, str] = EbayMarketplace.US,
    ) -> PolicyAssessment:
        marketplace_id = self._resolve_marketplace(marketplace)

        findings: List[PolicyFinding] = []

        for rule in SELLER_LEVEL_RULES:
            try:
                finding = rule(seller_data, marketplace_id)
                if finding is not None:
                    findings.append(finding)
            except Exception as e:
                logger.warning(
                    f"Seller rule {rule.__name__} failed: {e}. Skipping."
                )
                continue

        overall = self._compute_overall_risk(findings)

        return PolicyAssessment(
            marketplace=marketplace_id,
            item_id=None,
            title=f"Seller: {seller_data.get('seller_username', 'unknown')}",
            findings=findings,
            overall_risk=overall,
            policy_version=POLICY_VERSION,
        )

    def _resolve_marketplace(self, marketplace) -> str:
        if isinstance(marketplace, EbayMarketplace):
            return marketplace.value
        if isinstance(marketplace, str):
            try:
                return EbayMarketplace.from_id(marketplace).value
            except ValueError:
                logger.warning(
                    f"Unknown marketplace '{marketplace}', "
                    "defaulting to EBAY_US"
                )
                return EbayMarketplace.US.value
        return EbayMarketplace.US.value

    def _compute_overall_risk(
        self,
        findings: List[PolicyFinding],
    ) -> PolicyRiskLevel:
        """
        Compute overall risk using severity floor:
        the overall risk is the highest priority among all findings.
        HIGH findings can NEVER be silently downgraded.
        """
        if not findings:
            return PolicyRiskLevel.LOW

        # Find the finding with the highest priority
        highest_priority_finding = max(
            findings, key=lambda f: f.risk_level.priority
        )
        return highest_priority_finding.risk_level

    def _empty_assessment(
        self,
        marketplace_id: str,
    ) -> PolicyAssessment:
        return PolicyAssessment(
            marketplace=marketplace_id,
            item_id=None,
            title=None,
            findings=[],
            overall_risk=PolicyRiskLevel.REVIEW_REQUIRED,
            policy_version=POLICY_VERSION,
        )