"""
eBay policy rule definitions.
"""
import re
from typing import Callable, List, Optional, Set

from .models import (
    DetectionConfidence,
    EvidenceStrength,
    PolicyFinding,
    PolicyRiskCategory,
    PolicyRiskLevel,
    PolicySource,
    PolicyVerificationStatus,
)

# Policy Sources
SOURCE_PROHIBITED_RESTRICTED = PolicySource(
    name="eBay Prohibited and Restricted Items",
    url="https://www.ebay.com/help/policies/prohibited-restricted-items/prohibited-restricted-items",
    verification_status=PolicyVerificationStatus.HEURISTIC,
)

SOURCE_SELLING_PRACTICES = PolicySource(
    name="eBay Selling Practices Policy",
    url="https://www.ebay.com/help/policies/selling-policies/selling-practices-policy",
    verification_status=PolicyVerificationStatus.HEURISTIC,
)

SOURCE_PRODUCT_SAFETY = PolicySource(
    name="eBay Product Safety Policy",
    url="https://www.ebay.com/help/policies/prohibited-restricted-items/product-safety-policy",
    verification_status=PolicyVerificationStatus.HEURISTIC,
)

SOURCE_HAZARDOUS_MATERIALS = PolicySource(
    name="eBay Hazardous Materials Policy",
    url="https://www.ebay.com/help/policies/prohibited-restricted-items/hazardous-materials-policy",
    verification_status=PolicyVerificationStatus.HEURISTIC,
)

SOURCE_COUNTERFEIT = PolicySource(
    name="eBay Counterfeit / VeRO",
    url="https://www.ebay.com/help/policies/prohibited-restricted-items/counterfeit-item-policy",
    verification_status=PolicyVerificationStatus.HEURISTIC,
)

SOURCE_DROPSHIPPING = PolicySource(
    name="eBay Drop Shipping Policy",
    url="https://www.ebay.com/help/policies/selling-policies/selling-practices-policy/drop-shipping",
    verification_status=PolicyVerificationStatus.HEURISTIC,
)

SOURCE_SELLER_STANDARDS = PolicySource(
    name="eBay Seller Performance / Standards",
    url="https://www.ebay.com/help/policies/selling-policies/seller-performance-policy",
    verification_status=PolicyVerificationStatus.HEURISTIC,
)

PROHIBITED_SIGNALS = {
    "firearm", "handgun", "rifle", "shotgun", "ammunition",
    "explosive", "grenade", "silencer",
    "marijuana", "cannabis", "cocaine", "heroin", "methamphetamine",
    "human remains", "human skull",
    "ivory", "elephant tusk", "rhino horn",
    "counterfeit currency", "fake currency",
}

RESTRICTED_SIGNALS = {
    "alcohol", "wine", "beer", "spirits", "vodka", "whiskey",
    "tobacco", "cigarette", "cigar", "vape", "e-cigarette",
    "prescription", "medication", "pharmaceutical",
    "knife", "sword", "blade", "dagger", "machete",
    "pepper spray", "mace",
    "adult", "18+",
}

ELIGIBILITY_SIGNALS = {
    "bicycle helmet", "bike helmet",
    "car seat", "child seat", "infant seat", "booster seat",
    "crib", "cot",
    "hoverboard", "self balancing scooter",
    "trading card graded", "psa graded", "bgs graded",
    "trading card sealed", "wax box", "booster box",
}

SAFETY_SIGNALS = {
    "recall", "recalled",
    "toy magnet", "high-powered magnet",
    "children toy", "kids toy", "infant toy",
    "baby product",
    "medical device",
}

HAZMAT_SIGNALS = {
    "lithium battery", "li-ion battery", "lipo battery",
    "flammable", "combustible",
    "corrosive",
    "radioactive", "uranium",
    "aerosol", "propane", "butane",
    "explosive powder", "gunpowder",
    "mercury", "asbestos",
    "pesticide", "herbicide", "insecticide",
}

BRAND_AUTHENTICITY_SENSITIVE = {
    "apple", "samsung", "sony", "nike", "adidas",
    "louis vuitton", "gucci", "chanel", "prada", "hermes",
    "rolex", "omega", "cartier",
    "supreme", "off-white", "yeezy",
    "pokemon", "magic the gathering",
}

COUNTERFEIT_LANGUAGE = {
    "replica", "inspired by", "style of", "look alike",
    "unbranded", "generic version",
    "aaa quality", "1:1 copy", "mirror image",
}

_pattern_cache: dict = {}


def _compile_signal_pattern(signals: Set[str]) -> re.Pattern:
    key = frozenset(signals)
    if key in _pattern_cache:
        return _pattern_cache[key]
    sorted_signals = sorted(signals, key=len, reverse=True)
    escaped = [re.escape(s) for s in sorted_signals]
    pattern_str = r"(?<!\w)(?:" + "|".join(escaped) + r")(?!\w)"
    pattern = re.compile(pattern_str, re.IGNORECASE)
    _pattern_cache[key] = pattern
    return pattern


def _find_signal_match(text: str, signals: Set[str]) -> Optional[str]:
    if not text or not signals:
        return None
    pattern = _compile_signal_pattern(signals)
    match = pattern.search(text)
    if match:
        return match.group(0).lower()
    return None


def _get_supplier_processing_days(supplier: Optional[dict]) -> Optional[int]:
    """Extract supplier processing time safely from supplier dict."""
    if not supplier or not isinstance(supplier, dict):
        return None
    shipping = supplier.get("shipping_options")
    if not shipping or not isinstance(shipping, list):
        return None
    if len(shipping) == 0 or not isinstance(shipping[0], dict):
        return None
    first = shipping[0]
    days_max = first.get("estimated_days_max")
    days_min = first.get("estimated_days_min")
    if days_max is not None:
        return int(days_max)
    if days_min is not None:
        return int(days_min)
    return None


def rule_prohibited_item(
    listing: dict,
    supplier: Optional[dict],
    marketplace: str,
) -> Optional[PolicyFinding]:
    title = listing.get("title", "")
    match = _find_signal_match(title, PROHIBITED_SIGNALS)
    if match is None:
        return None

    return PolicyFinding(
        category=PolicyRiskCategory.PROHIBITED_ITEM,
        risk_level=PolicyRiskLevel.HIGH,
        reason=(
            f"Title contains signal ('{match}') associated with "
            "prohibited/highly-restricted items."
        ),
        evidence=f"Word-boundary match in title: '{match}'",
        evidence_strength=EvidenceStrength.LIKELY,
        detection_confidence=DetectionConfidence.HIGH,
        action=(
            "Verify against eBay's Prohibited and Restricted Items policy. "
            "Keyword match alone is not proof of violation."
        ),
        source=SOURCE_PROHIBITED_RESTRICTED,
        rule_id="prohibited_item_v2",
    )


def rule_restricted_item(
    listing: dict,
    supplier: Optional[dict],
    marketplace: str,
) -> Optional[PolicyFinding]:
    title = listing.get("title", "")
    match = _find_signal_match(title, RESTRICTED_SIGNALS)
    if match is None:
        return None

    return PolicyFinding(
        category=PolicyRiskCategory.RESTRICTED_ITEM,
        risk_level=PolicyRiskLevel.MEDIUM,
        reason=(
            f"Title contains signal ('{match}') associated with "
            "regulated/restricted items."
        ),
        evidence=f"Word-boundary match in title: '{match}'",
        evidence_strength=EvidenceStrength.POTENTIAL,
        detection_confidence=DetectionConfidence.HIGH,
        action="Review eBay's category-specific policies for restrictions.",
        source=SOURCE_PROHIBITED_RESTRICTED,
        rule_id="restricted_item_v2",
    )


def rule_eligibility_required(
    listing: dict,
    supplier: Optional[dict],
    marketplace: str,
) -> Optional[PolicyFinding]:
    title = listing.get("title", "")
    match = _find_signal_match(title, ELIGIBILITY_SIGNALS)
    if match is None:
        return None

    return PolicyFinding(
        category=PolicyRiskCategory.ELIGIBILITY_REQUIRED,
        risk_level=PolicyRiskLevel.MEDIUM,
        reason=(
            f"Title contains signal ('{match}') for products that may "
            "require seller eligibility or approval."
        ),
        evidence=f"Word-boundary match in title: '{match}'",
        evidence_strength=EvidenceStrength.POTENTIAL,
        detection_confidence=DetectionConfidence.HIGH,
        action="Check seller eligibility requirements for this category.",
        source=SOURCE_PROHIBITED_RESTRICTED,
        rule_id="eligibility_v2",
    )


def rule_product_safety(
    listing: dict,
    supplier: Optional[dict],
    marketplace: str,
) -> Optional[PolicyFinding]:
    title = listing.get("title", "")
    match = _find_signal_match(title, SAFETY_SIGNALS)
    if match is None:
        return None

    is_recall = match in ("recall", "recalled")
    risk = PolicyRiskLevel.HIGH if is_recall else PolicyRiskLevel.REVIEW_REQUIRED
    strength = EvidenceStrength.LIKELY if is_recall else EvidenceStrength.POTENTIAL

    return PolicyFinding(
        category=PolicyRiskCategory.PRODUCT_SAFETY,
        risk_level=risk,
        reason=(
            f"Title contains signal ('{match}') associated with a "
            "product safety category."
        ),
        evidence=f"Word-boundary match in title: '{match}'",
        evidence_strength=strength,
        detection_confidence=DetectionConfidence.HIGH,
        action="Verify product against eBay's Product Safety Policy.",
        source=SOURCE_PRODUCT_SAFETY,
        rule_id="product_safety_v2",
    )


def rule_hazardous_material(
    listing: dict,
    supplier: Optional[dict],
    marketplace: str,
) -> Optional[PolicyFinding]:
    title = listing.get("title", "")
    match = _find_signal_match(title, HAZMAT_SIGNALS)
    if match is None:
        return None

    return PolicyFinding(
        category=PolicyRiskCategory.HAZARDOUS_MATERIAL,
        risk_level=PolicyRiskLevel.REVIEW_REQUIRED,
        reason=(
            f"Title contains signal ('{match}') that may indicate a "
            "hazardous material. Shipping restrictions likely apply."
        ),
        evidence=f"Word-boundary match in title: '{match}'",
        evidence_strength=EvidenceStrength.POTENTIAL,
        detection_confidence=DetectionConfidence.HIGH,
        action="Review eBay's Hazardous Materials Policy and shipping rules.",
        source=SOURCE_HAZARDOUS_MATERIALS,
        rule_id="hazmat_v2",
    )


def rule_ip_authenticity(
    listing: dict,
    supplier: Optional[dict],
    marketplace: str,
) -> Optional[PolicyFinding]:
    title = listing.get("title", "")

    lang_match = _find_signal_match(title, COUNTERFEIT_LANGUAGE)
    if lang_match:
        return PolicyFinding(
            category=PolicyRiskCategory.IP_AUTHENTICITY,
            risk_level=PolicyRiskLevel.HIGH,
            reason=(
                f"Title contains language ('{lang_match}') sometimes "
                "associated with counterfeit or replica products."
            ),
            evidence=f"Word-boundary match in title: '{lang_match}'",
            evidence_strength=EvidenceStrength.LIKELY,
            detection_confidence=DetectionConfidence.HIGH,
            action="Do NOT list replica, counterfeit, or unauthorized copies.",
            source=SOURCE_COUNTERFEIT,
            rule_id="ip_language_v2",
        )

    brand_field = (listing.get("product_brand") or "").lower().strip()
    detected_brand = _find_signal_match(title, BRAND_AUTHENTICITY_SENSITIVE)
    if not detected_brand and brand_field in BRAND_AUTHENTICITY_SENSITIVE:
        detected_brand = brand_field

    if detected_brand is None:
        return None

    has_generic_supplier = False
    if supplier and isinstance(supplier, dict):
        if supplier.get("source", "") == "mock":
            has_generic_supplier = True

    if has_generic_supplier:
        return PolicyFinding(
            category=PolicyRiskCategory.IP_AUTHENTICITY,
            risk_level=PolicyRiskLevel.REVIEW_REQUIRED,
            reason=(
                f"Branded product ('{detected_brand}') paired with "
                "supplier that is not a verified authorized reseller."
            ),
            evidence=f"Brand '{detected_brand}' detected; supplier not verified",
            evidence_strength=EvidenceStrength.POTENTIAL,
            detection_confidence=DetectionConfidence.MEDIUM,
            action="Verify authorization to resell this brand.",
            source=SOURCE_COUNTERFEIT,
            rule_id="ip_brand_supplier_v2",
        )

    return PolicyFinding(
        category=PolicyRiskCategory.IP_AUTHENTICITY,
        risk_level=PolicyRiskLevel.REVIEW_REQUIRED,
        reason=(
            f"Branded product detected ('{detected_brand}'). "
            "Authenticity should be verified before listing."
        ),
        evidence=f"Brand '{detected_brand}' detected",
        evidence_strength=EvidenceStrength.POTENTIAL,
        detection_confidence=DetectionConfidence.MEDIUM,
        action="Verify product is authentic and you are authorized to sell.",
        source=SOURCE_COUNTERFEIT,
        rule_id="ip_brand_v2",
    )


def rule_shipping_feasibility(
    listing: dict,
    supplier: Optional[dict],
    marketplace: str,
) -> Optional[PolicyFinding]:
    if not supplier:
        return None

    processing_days = _get_supplier_processing_days(supplier)
    if processing_days is None:
        return None

    if processing_days > 30:
        return PolicyFinding(
            category=PolicyRiskCategory.SHIPPING,
            risk_level=PolicyRiskLevel.MEDIUM,
            reason=(
                f"Supplier estimated delivery time ({processing_days} days) "
                "may exceed typical buyer expectations."
            ),
            evidence=f"Supplier estimated_days_max: {processing_days}",
            evidence_strength=EvidenceStrength.LIKELY,
            detection_confidence=DetectionConfidence.HIGH,
            action="Set realistic handling time in listing.",
            source=SOURCE_SELLING_PRACTICES,
            rule_id="shipping_slow_v2",
        )
    elif processing_days > 15:
        return PolicyFinding(
            category=PolicyRiskCategory.SHIPPING,
            risk_level=PolicyRiskLevel.REVIEW_REQUIRED,
            reason=(
                f"Supplier estimated delivery time ({processing_days} days) "
                "requires careful handling time configuration."
            ),
            evidence=f"Supplier estimated_days_max: {processing_days}",
            evidence_strength=EvidenceStrength.POTENTIAL,
            detection_confidence=DetectionConfidence.HIGH,
            action="Ensure eBay listing handling time reflects supplier delivery.",
            source=SOURCE_SELLING_PRACTICES,
            rule_id="shipping_moderate_v2",
        )

    return None


def rule_shipping_data_missing(
    listing: dict,
    supplier: Optional[dict],
    marketplace: str,
) -> Optional[PolicyFinding]:
    if supplier is None:
        return None

    processing = _get_supplier_processing_days(supplier)
    if processing is None:
        return PolicyFinding(
            category=PolicyRiskCategory.SHIPPING,
            risk_level=PolicyRiskLevel.REVIEW_REQUIRED,
            reason=(
                "Supplier is present but shipping estimates are not "
                "available. Cannot verify shipping feasibility."
            ),
            evidence="Supplier shipping_options missing or empty",
            evidence_strength=EvidenceStrength.INSUFFICIENT,
            detection_confidence=DetectionConfidence.HIGH,
            action="Confirm actual supplier shipping timeline before listing.",
            source=SOURCE_SELLING_PRACTICES,
            rule_id="shipping_unknown_v2",
        )

    return None


def rule_dropshipping_sourcing(
    listing: dict,
    supplier: Optional[dict],
    marketplace: str,
) -> Optional[PolicyFinding]:
    if not supplier or not isinstance(supplier, dict):
        return None

    supplier_source = supplier.get("source", "")
    is_retail_marketplace = supplier_source in ("mock", "aliexpress")

    if is_retail_marketplace:
        return PolicyFinding(
            category=PolicyRiskCategory.DROPSHIPPING,
            risk_level=PolicyRiskLevel.MEDIUM,
            reason=(
                "Supplier appears to be a retail marketplace (AliExpress). "
                "eBay's dropshipping policy may restrict sourcing from "
                "other retail marketplaces without direct fulfillment."
            ),
            evidence=f"Supplier source: '{supplier_source}'",
            evidence_strength=EvidenceStrength.POTENTIAL,
            detection_confidence=DetectionConfidence.HIGH,
            action="Review eBay's drop shipping policy.",
            source=SOURCE_DROPSHIPPING,
            rule_id="dropshipping_retail_v2",
        )

    return None


def rule_listing_accuracy_condition(
    listing: dict,
    supplier: Optional[dict],
    marketplace: str,
) -> Optional[PolicyFinding]:
    if not supplier or not isinstance(supplier, dict):
        return None

    listing_condition = (listing.get("condition") or "").lower()
    if not listing_condition:
        return None

    supplier_attrs = supplier.get("attributes", {}) or {}
    supplier_condition = str(supplier_attrs.get("condition", "")).lower()

    if (
        "new" in listing_condition
        and supplier_condition
        and "new" not in supplier_condition
    ):
        return PolicyFinding(
            category=PolicyRiskCategory.LISTING_ACCURACY,
            risk_level=PolicyRiskLevel.MEDIUM,
            reason=(
                f"Listing condition ('{listing_condition}') may not match "
                f"supplier condition ('{supplier_condition}')."
            ),
            evidence=(
                f"Listing condition: '{listing_condition}'; "
                f"supplier condition: '{supplier_condition}'"
            ),
            evidence_strength=EvidenceStrength.POTENTIAL,
            detection_confidence=DetectionConfidence.MEDIUM,
            action="Verify actual product condition matches listing.",
            source=SOURCE_SELLING_PRACTICES,
            rule_id="listing_condition_mismatch_v2",
        )

    return None


def rule_seller_performance(
    seller_data: dict,
    marketplace: str,
) -> Optional[PolicyFinding]:
    feedback_pct = seller_data.get("seller_feedback_percentage")
    if feedback_pct is None:
        return None

    try:
        feedback = float(feedback_pct)
    except (ValueError, TypeError):
        return None

    if feedback < 90:
        return PolicyFinding(
            category=PolicyRiskCategory.SELLER_PERFORMANCE,
            risk_level=PolicyRiskLevel.HIGH,
            reason=(
                f"Seller feedback ({feedback}%) is significantly below "
                "typical eBay seller performance expectations."
            ),
            evidence=f"Seller feedback percentage: {feedback}%",
            evidence_strength=EvidenceStrength.CONFIRMED,
            detection_confidence=DetectionConfidence.HIGH,
            action="Low seller feedback may impact search visibility.",
            source=SOURCE_SELLER_STANDARDS,
            rule_id="seller_perf_low_v2",
        )
    elif feedback < 95:
        return PolicyFinding(
            category=PolicyRiskCategory.SELLER_PERFORMANCE,
            risk_level=PolicyRiskLevel.MEDIUM,
            reason=(
                f"Seller feedback ({feedback}%) is below typical "
                "high-performance thresholds."
            ),
            evidence=f"Seller feedback percentage: {feedback}%",
            evidence_strength=EvidenceStrength.CONFIRMED,
            detection_confidence=DetectionConfidence.HIGH,
            action="Monitor performance metrics.",
            source=SOURCE_SELLER_STANDARDS,
            rule_id="seller_perf_medium_v2",
        )

    return None


PRODUCT_LEVEL_RULES: List[Callable] = [
    rule_prohibited_item,
    rule_restricted_item,
    rule_eligibility_required,
    rule_product_safety,
    rule_hazardous_material,
    rule_ip_authenticity,
    rule_shipping_feasibility,
    rule_shipping_data_missing,
    rule_dropshipping_sourcing,
    rule_listing_accuracy_condition,
]

SELLER_LEVEL_RULES: List[Callable] = [
    rule_seller_performance,
]

POLICY_VERSION = "mvp-baseline-2025"