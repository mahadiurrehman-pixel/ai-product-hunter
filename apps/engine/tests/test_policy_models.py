"""Tests for policy data models."""
"""Tests for policy data models."""
from datetime import datetime

import pytest

from services.policy.models import (
    EvidenceStrength,
    PolicyAssessment,
    PolicyFinding,
    PolicyRiskCategory,
    PolicyRiskLevel,
    PolicySource,
    PolicyVerificationStatus,
)


class TestPolicyRiskLevel:
    def test_all_levels_have_badges(self):
        for level in PolicyRiskLevel:
            assert level.badge != ""
            assert len(level.badge) > 0

    def test_low_badge_has_green(self):
        assert "🟢" in PolicyRiskLevel.LOW.badge

    def test_medium_badge_has_yellow(self):
        assert "🟡" in PolicyRiskLevel.MEDIUM.badge

    def test_high_badge_has_red(self):
        assert "🔴" in PolicyRiskLevel.HIGH.badge

    def test_review_badge_has_white(self):
        assert "⚪" in PolicyRiskLevel.REVIEW_REQUIRED.badge


class TestPolicyRiskCategory:
    def test_product_level_categories_exist(self):
        assert PolicyRiskCategory.PROHIBITED_ITEM
        assert PolicyRiskCategory.RESTRICTED_ITEM
        assert PolicyRiskCategory.ELIGIBILITY_REQUIRED
        assert PolicyRiskCategory.PRODUCT_SAFETY
        assert PolicyRiskCategory.HAZARDOUS_MATERIAL
        assert PolicyRiskCategory.IP_AUTHENTICITY

    def test_listing_categories_exist(self):
        assert PolicyRiskCategory.LISTING_ACCURACY
        assert PolicyRiskCategory.SHIPPING
        assert PolicyRiskCategory.DROPSHIPPING

    def test_seller_categories_exist(self):
        assert PolicyRiskCategory.SELLER_BEHAVIOR
        assert PolicyRiskCategory.SELLER_PERFORMANCE


class TestPolicySource:
    def test_source_has_verification_status(self):
        src = PolicySource(name="Test", url="https://example.com")
        assert src.verification_status == PolicyVerificationStatus.HEURISTIC

    def test_source_is_immutable(self):
        src = PolicySource(name="Test", url="https://example.com")
        with pytest.raises(Exception):
            src.name = "Changed"

    def test_source_to_dict(self):
        src = PolicySource(name="Test", url="https://example.com")
        d = src.to_dict()
        assert d["name"] == "Test"
        assert d["url"] == "https://example.com"
        assert "verification_status" in d


class TestPolicyFinding:
    @pytest.fixture
    def sample_source(self):
        return PolicySource(
            name="Test Policy",
            url="https://example.com/policy",
        )

    def test_finding_creation(self, sample_source):
        f = PolicyFinding(
            category=PolicyRiskCategory.RESTRICTED_ITEM,
            risk_level=PolicyRiskLevel.MEDIUM,
            reason="Test reason",
            evidence="Test evidence",
            evidence_strength=EvidenceStrength.POTENTIAL,
            action="Test action",
            source=sample_source,
            rule_id="test_rule_v1",
        )
        assert f.category == PolicyRiskCategory.RESTRICTED_ITEM
        assert f.risk_level == PolicyRiskLevel.MEDIUM

    def test_finding_to_dict(self, sample_source):
        f = PolicyFinding(
            category=PolicyRiskCategory.PROHIBITED_ITEM,
            risk_level=PolicyRiskLevel.HIGH,
            reason="Test",
            evidence="Test",
            evidence_strength=EvidenceStrength.LIKELY,
            action="Test",
            source=sample_source,
            rule_id="test_v1",
        )
        d = f.to_dict()
        assert d["category"] == "prohibited_item"
        assert d["risk_level"] == "high"
        assert "risk_badge" in d
        assert d["rule_id"] == "test_v1"
        assert "source" in d


class TestPolicyAssessment:
    def test_empty_assessment_defaults(self):
        a = PolicyAssessment(
            marketplace="EBAY_US",
            item_id="v1|001|0",
            title="Test Product",
        )
        assert a.overall_risk == PolicyRiskLevel.LOW
        assert a.findings == []
        assert a.policy_version == "mvp-baseline-2025"

    def test_assessment_has_disclaimer(self):
        a = PolicyAssessment(
            marketplace="EBAY_US",
            item_id="v1|001|0",
            title="Test",
        )
        assert "not legal advice" in a.disclaimer.lower()
        assert "guarantee" in a.disclaimer.lower()

    def test_assessment_has_limitations(self):
        a = PolicyAssessment(
            marketplace="EBAY_US",
            item_id="v1|001|0",
            title="Test",
        )
        assert len(a.limitations) >= 3
        # Every limitation should have warning emoji
        for lim in a.limitations:
            assert "⚠️" in lim

    def test_findings_by_category(self):
        src = PolicySource(name="T", url="https://x.com")
        f1 = PolicyFinding(
            category=PolicyRiskCategory.SHIPPING,
            risk_level=PolicyRiskLevel.MEDIUM,
            reason="", evidence="", evidence_strength=EvidenceStrength.POTENTIAL,
            action="", source=src, rule_id="r1",
        )
        f2 = PolicyFinding(
            category=PolicyRiskCategory.SHIPPING,
            risk_level=PolicyRiskLevel.LOW,
            reason="", evidence="", evidence_strength=EvidenceStrength.POTENTIAL,
            action="", source=src, rule_id="r2",
        )
        a = PolicyAssessment(
            marketplace="EBAY_US", item_id=None, title=None,
            findings=[f1, f2],
        )
        grouped = a.findings_by_category
        assert "shipping" in grouped
        assert len(grouped["shipping"]) == 2

    def test_has_high_risk_true(self):
        src = PolicySource(name="T", url="https://x.com")
        f = PolicyFinding(
            category=PolicyRiskCategory.PROHIBITED_ITEM,
            risk_level=PolicyRiskLevel.HIGH,
            reason="", evidence="", evidence_strength=EvidenceStrength.CONFIRMED,
            action="", source=src, rule_id="r1",
        )
        a = PolicyAssessment(
            marketplace="EBAY_US", item_id=None, title=None,
            findings=[f],
        )
        assert a.has_high_risk is True

    def test_has_high_risk_false(self):
        a = PolicyAssessment(
            marketplace="EBAY_US", item_id=None, title=None,
        )
        assert a.has_high_risk is False

    def test_to_dict_complete(self):
        a = PolicyAssessment(
            marketplace="EBAY_US",
            item_id="v1|001|0",
            title="Test",
        )
        d = a.to_dict()
        required = [
            "overall_risk", "overall_risk_badge", "marketplace",
            "item_id", "title", "findings", "finding_count",
            "disclaimer", "limitations", "policy_version",
            "assessed_at",
        ]
        for key in required:
            assert key in d, f"Missing: {key}"