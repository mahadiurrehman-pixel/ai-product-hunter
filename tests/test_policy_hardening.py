"""
Tests for the safe hardening improvements to the policy checker.

Covers:
- New PolicyVerificationStatus enum
- New DetectionConfidence enum
- Word-boundary keyword matching (false positive prevention)
- Rule-level severity floor (HIGH never downgraded)
- PolicySource verification metadata invariants
- Honest disclaimer/limitations
"""
from decimal import Decimal

import pytest

from services.policy import (
    DetectionConfidence,
    PolicyAssessment,
    PolicyChecker,
    PolicyFinding,
    PolicyRiskCategory,
    PolicyRiskLevel,
    PolicySource,
    PolicyVerificationStatus,
)
from services.policy.rules import (
    _find_signal_match,
    HAZMAT_SIGNALS,
    PROHIBITED_SIGNALS,
    BRAND_AUTHENTICITY_SENSITIVE,
)


# =============================================================================
# PolicyVerificationStatus enum
# =============================================================================

class TestPolicyVerificationStatus:
    def test_three_status_levels_exist(self):
        assert PolicyVerificationStatus.HEURISTIC
        assert PolicyVerificationStatus.REQUIRES_MANUAL_VERIFICATION
        assert PolicyVerificationStatus.VERIFIED_OFFICIAL_SOURCE

    def test_heuristic_is_default(self):
        src = PolicySource(name="Test")
        assert src.verification_status == PolicyVerificationStatus.HEURISTIC

    def test_string_values_stable(self):
        assert (
            PolicyVerificationStatus.HEURISTIC.value
            == "heuristic_pattern_matching"
        )
        assert (
            PolicyVerificationStatus.VERIFIED_OFFICIAL_SOURCE.value
            == "verified_official_source"
        )


# =============================================================================
# DetectionConfidence enum
# =============================================================================

class TestDetectionConfidence:
    def test_three_confidence_levels(self):
        assert DetectionConfidence.HIGH
        assert DetectionConfidence.MEDIUM
        assert DetectionConfidence.LOW


# =============================================================================
# PolicySource invariants
# =============================================================================

class TestPolicySourceInvariants:
    def test_heuristic_needs_no_url(self):
        # Should not raise
        src = PolicySource(
            name="Heuristic Rule",
            verification_status=PolicyVerificationStatus.HEURISTIC,
        )
        assert src.source_url is None
        assert src.last_verified is None

    def test_verified_requires_url(self):
        with pytest.raises(ValueError) as exc_info:
            PolicySource(
                name="Fake Verified",
                verification_status=(
                    PolicyVerificationStatus.VERIFIED_OFFICIAL_SOURCE
                ),
                # Missing source_url and last_verified
            )
        assert "VERIFIED_OFFICIAL_SOURCE" in str(exc_info.value)
        assert "source_url" in str(exc_info.value)

    def test_verified_requires_last_verified(self):
        with pytest.raises(ValueError):
            PolicySource(
                name="Fake Verified",
                verification_status=(
                    PolicyVerificationStatus.VERIFIED_OFFICIAL_SOURCE
                ),
                source_url="https://example.com",
                # Missing last_verified
            )

    def test_valid_verified_source(self):
        src = PolicySource(
            name="Valid Verified Source",
            verification_status=(
                PolicyVerificationStatus.VERIFIED_OFFICIAL_SOURCE
            ),
            source_url="https://www.ebay.com/help/policies/example",
            last_verified="2025-01-15",
        )
        assert src.verification_status == (
            PolicyVerificationStatus.VERIFIED_OFFICIAL_SOURCE
        )
        assert src.source_url == "https://www.ebay.com/help/policies/example"

    def test_source_to_dict_includes_verification_status(self):
        src = PolicySource(name="Test")
        d = src.to_dict()
        assert d["verification_status"] == "heuristic_pattern_matching"
        assert d["source_url"] is None
        assert d["last_verified"] is None


# =============================================================================
# Word-boundary keyword matching
# =============================================================================

class TestWordBoundaryMatching:
    """
    Critical: verify that keyword matching uses word boundaries and
    does not false-positive on partial word matches.
    """

    def test_acid_does_not_match_placid(self):
        # "acid" is a hazmat signal — must not match "placid"
        assert _find_signal_match("Placid Lake View", {"acid"}) is None

    def test_acid_does_not_match_acidic(self):
        assert _find_signal_match("mildly acidic soap", {"acid"}) is None

    def test_acid_matches_standalone(self):
        # This test only passes if "acid" is in the signal set
        assert _find_signal_match("industrial acid cleaner", {"acid"}) == "acid"

    def test_case_does_not_match_casebook(self):
        assert _find_signal_match("legal casebook", {"case"}) is None

    def test_case_does_not_match_staircase(self):
        assert _find_signal_match("wooden staircase design", {"case"}) is None

    def test_case_matches_standalone_word(self):
        assert _find_signal_match(
            "phone case iphone", {"case"}
        ) == "case"

    def test_nike_matches_word(self):
        assert _find_signal_match(
            "Nike Air Max", BRAND_AUTHENTICITY_SENSITIVE
        ) == "nike"

    def test_nike_does_not_match_partial(self):
        # Purely to prove word boundary works — "nike" should not match
        # if embedded in a longer non-space-separated string
        assert _find_signal_match("sniker fake", {"nike"}) is None

    def test_multi_word_phrase_matches(self):
        assert _find_signal_match(
            "Lithium Battery Pack 12V", HAZMAT_SIGNALS
        ) == "lithium battery"

    def test_multi_word_phrase_case_insensitive(self):
        assert _find_signal_match(
            "LITHIUM BATTERY new", HAZMAT_SIGNALS
        ) == "lithium battery"

    def test_hyphenated_multi_word(self):
        # Li-Ion matches "li-ion battery"
        result = _find_signal_match(
            "Li-Ion Battery Cell", HAZMAT_SIGNALS
        )
        # This should match because li-ion battery is in HAZMAT_SIGNALS
        assert result is not None
        assert "battery" in result

    def test_empty_text_no_match(self):
        assert _find_signal_match("", HAZMAT_SIGNALS) is None

    def test_empty_signals_no_match(self):
        assert _find_signal_match("some text", set()) is None

    def test_none_text_no_match(self):
        assert _find_signal_match(None, HAZMAT_SIGNALS) is None

    def test_gunpowder_matches_prohibited(self):
        # gunpowder is a hazmat signal
        assert _find_signal_match(
            "old gunpowder tin", HAZMAT_SIGNALS
        ) == "gunpowder"

    def test_handgun_matches_prohibited(self):
        assert _find_signal_match(
            "vintage handgun for sale", PROHIBITED_SIGNALS
        ) == "handgun"

    def test_normal_earbuds_no_false_positives(self):
        # Real-world product should not trigger anything
        title = "Wireless Bluetooth Earbuds with Charging Case"
        assert _find_signal_match(title, PROHIBITED_SIGNALS) is None
        assert _find_signal_match(title, HAZMAT_SIGNALS) is None

    def test_normal_charger_no_hazmat_false_positive(self):
        title = "20W USB-C Fast Charger Wall Adapter"
        assert _find_signal_match(title, HAZMAT_SIGNALS) is None


# =============================================================================
# Rule-level severity floor
# =============================================================================

class TestSeverityFloor:
    """HIGH findings must never be silently downgraded during aggregation."""

    @pytest.fixture
    def checker(self):
        return PolicyChecker()

    def test_high_finding_dominates_over_low(self, checker):
        """Even if 5 LOW findings exist, one HIGH → overall HIGH."""
        src = PolicySource(name="test")
        # Manually construct findings
        low_findings = [
            PolicyFinding(
                category=PolicyRiskCategory.SHIPPING,
                risk_level=PolicyRiskLevel.LOW,
                reason="",
                evidence="",
                evidence_strength="potential",
                action="",
                source=src,
                rule_id=f"low_{i}",
            )
            for i in range(5)
        ]
        high_finding = PolicyFinding(
            category=PolicyRiskCategory.PROHIBITED_ITEM,
            risk_level=PolicyRiskLevel.HIGH,
            reason="",
            evidence="",
            evidence_strength="likely",
            action="",
            source=src,
            rule_id="high_1",
        )

        overall = checker._compute_overall_risk(low_findings + [high_finding])
        assert overall == PolicyRiskLevel.HIGH

    def test_high_finding_dominates_over_medium(self, checker):
        src = PolicySource(name="test")
        medium_findings = [
            PolicyFinding(
                category=PolicyRiskCategory.SHIPPING,
                risk_level=PolicyRiskLevel.MEDIUM,
                reason="",
                evidence="",
                evidence_strength="potential",
                action="",
                source=src,
                rule_id=f"m_{i}",
            )
            for i in range(3)
        ]
        high_finding = PolicyFinding(
            category=PolicyRiskCategory.PROHIBITED_ITEM,
            risk_level=PolicyRiskLevel.HIGH,
            reason="",
            evidence="",
            evidence_strength="likely",
            action="",
            source=src,
            rule_id="h1",
        )

        overall = checker._compute_overall_risk(
            medium_findings + [high_finding]
        )
        assert overall == PolicyRiskLevel.HIGH

    def test_medium_beats_review_required(self, checker):
        src = PolicySource(name="test")
        findings = [
            PolicyFinding(
                category=PolicyRiskCategory.SHIPPING,
                risk_level=PolicyRiskLevel.REVIEW_REQUIRED,
                reason="",
                evidence="",
                evidence_strength="insufficient",
                action="",
                source=src,
                rule_id="r1",
            ),
            PolicyFinding(
                category=PolicyRiskCategory.RESTRICTED_ITEM,
                risk_level=PolicyRiskLevel.MEDIUM,
                reason="",
                evidence="",
                evidence_strength="potential",
                action="",
                source=src,
                rule_id="m1",
            ),
        ]
        overall = checker._compute_overall_risk(findings)
        assert overall == PolicyRiskLevel.MEDIUM

    def test_review_required_beats_low(self, checker):
        src = PolicySource(name="test")
        findings = [
            PolicyFinding(
                category=PolicyRiskCategory.SHIPPING,
                risk_level=PolicyRiskLevel.LOW,
                reason="",
                evidence="",
                evidence_strength="potential",
                action="",
                source=src,
                rule_id="l1",
            ),
            PolicyFinding(
                category=PolicyRiskCategory.HAZARDOUS_MATERIAL,
                risk_level=PolicyRiskLevel.REVIEW_REQUIRED,
                reason="",
                evidence="",
                evidence_strength="insufficient",
                action="",
                source=src,
                rule_id="r1",
            ),
        ]
        overall = checker._compute_overall_risk(findings)
        assert overall == PolicyRiskLevel.REVIEW_REQUIRED

    def test_empty_findings_low(self, checker):
        assert checker._compute_overall_risk([]) == PolicyRiskLevel.LOW


# =============================================================================
# High-risk findings always visible
# =============================================================================

class TestHighRiskVisibility:
    """HIGH findings must always be surfaced in findings[] and helpers."""

    @pytest.fixture
    def checker(self):
        return PolicyChecker()

    def test_high_findings_property(self, checker):
        listing = {
            "item_id": "v1|1|0",
            "title": "Handgun for Sale",
            "price_value": Decimal("500"),
        }
        assessment = checker.check(listing)
        assert len(assessment.high_risk_findings) > 0
        assert assessment.has_high_risk is True

    def test_high_finding_count_in_dict(self, checker):
        listing = {
            "item_id": "v1|1|0",
            "title": "Rolex Replica Watch",
            "price_value": Decimal("50"),
        }
        assessment = checker.check(listing)
        d = assessment.to_dict()
        assert d["high_risk_finding_count"] > 0

    def test_no_high_finding_shows_zero(self, checker):
        listing = {
            "item_id": "v1|1|0",
            "title": "Wireless Bluetooth Earbuds",
            "price_value": Decimal("29.99"),
        }
        assessment = checker.check(listing)
        d = assessment.to_dict()
        assert d["high_risk_finding_count"] == 0


# =============================================================================
# Honest disclaimer
# =============================================================================

class TestHonestDisclaimer:
    @pytest.fixture
    def checker(self):
        return PolicyChecker()

    def test_disclaimer_mentions_pattern_based(self, checker):
        listing = {"item_id": "v1|1|0", "title": "Test", "price_value": Decimal("10")}
        assessment = checker.check(listing)
        assert "pattern-based" in assessment.disclaimer.lower()

    def test_disclaimer_not_legal_advice(self, checker):
        listing = {"item_id": "v1|1|0", "title": "Test", "price_value": Decimal("10")}
        assessment = checker.check(listing)
        assert "not legal" in assessment.disclaimer.lower()

    def test_disclaimer_verify_against_official(self, checker):
        listing = {"item_id": "v1|1|0", "title": "Test", "price_value": Decimal("10")}
        assessment = checker.check(listing)
        assert "verify" in assessment.disclaimer.lower()
        assert "official" in assessment.disclaimer.lower()

    def test_limitations_mention_heuristic(self, checker):
        listing = {"item_id": "v1|1|0", "title": "Test", "price_value": Decimal("10")}
        assessment = checker.check(listing)
        heuristic_mentioned = any(
            "heuristic" in lim.lower() for lim in assessment.limitations
        )
        assert heuristic_mentioned

    def test_limitations_distinguish_confidence_types(self, checker):
        listing = {"item_id": "v1|1|0", "title": "Test", "price_value": Decimal("10")}
        assessment = checker.check(listing)
        # Should explain detection vs policy confidence
        distinction_mentioned = any(
            "detection" in lim.lower() and "confidence" in lim.lower()
            for lim in assessment.limitations
        )
        assert distinction_mentioned


# =============================================================================
# Policy version honesty
# =============================================================================

class TestPolicyVersionHonesty:
    def test_version_marked_heuristic(self):
        from services.policy.rules import POLICY_VERSION
        assert "mvp-baseline-2025" in POLICY_VERSION.lower()

    def test_version_not_fake_2026_date(self):
        from services.policy.rules import POLICY_VERSION
        assert "2026" not in POLICY_VERSION


# =============================================================================
# Unverified findings count
# =============================================================================

class TestUnverifiedCount:
    @pytest.fixture
    def checker(self):
        return PolicyChecker()

    def test_all_current_findings_are_unverified(self, checker):
        """
        Since no rule has been marked VERIFIED_OFFICIAL_SOURCE,
        every finding should count as unverified.
        """
        listing = {
            "item_id": "v1|1|0",
            "title": "Handgun for Sale Cannabis Nike",
            "price_value": Decimal("100"),
        }
        assessment = checker.check(listing)
        assert (
            assessment.unverified_findings_count == len(assessment.findings)
        )

    def test_unverified_count_in_dict(self, checker):
        listing = {
            "item_id": "v1|1|0",
            "title": "Kitchen Knife Set",
            "price_value": Decimal("30"),
        }
        assessment = checker.check(listing)
        d = assessment.to_dict()
        assert "unverified_findings_count" in d


# =============================================================================
# Detection confidence on findings
# =============================================================================

class TestDetectionConfidenceOnFindings:
    @pytest.fixture
    def checker(self):
        return PolicyChecker()

    def test_findings_have_detection_confidence(self, checker):
        listing = {
            "item_id": "v1|1|0",
            "title": "Cannabis Grinder",
            "price_value": Decimal("15"),
        }
        assessment = checker.check(listing)
        for f in assessment.findings:
            assert isinstance(f.detection_confidence, DetectionConfidence)

    def test_detection_confidence_in_dict(self, checker):
        listing = {
            "item_id": "v1|1|0",
            "title": "Handgun for Sale",
            "price_value": Decimal("500"),
        }
        assessment = checker.check(listing)
        d = assessment.to_dict()
        for f in d["findings"]:
            assert "detection_confidence" in f


# =============================================================================
# Overall JSON serializability
# =============================================================================

class TestJSONSerializable:
    @pytest.fixture
    def checker(self):
        return PolicyChecker()

    def test_full_assessment_json_serializable(self, checker):
        import json
        listing = {
            "item_id": "v1|1|0",
            "title": "Nike Air Max Replica Style",
            "price_value": Decimal("50"),
            "product_brand": "Nike",
        }
        supplier = {
            "product_id": "ali_001",
            "source": "mock",
            "shipping_options": [
                {"estimated_days_min": 20, "estimated_days_max": 30}
            ],
        }
        assessment = checker.check(listing, supplier=supplier)
        d = assessment.to_dict()
        # Must be JSON-serializable
        json.dumps(d, default=str)