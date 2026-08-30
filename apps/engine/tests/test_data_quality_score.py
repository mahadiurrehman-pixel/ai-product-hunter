"""Tests for Data Quality Score (DQS)."""
import pytest
from services.product_identity import (
    ProductIdentityBuilder, ConflictDetector,
    DataQualityAnalyzer, DataQualityScore, DQSLevel,
    QualityFlag,
)
from services.product_identity.models import ProductIdentity
from services.product_identity.attributes import (
    CanonicalAttribute, AttributeStatus,
)


@pytest.fixture
def analyzer():
    return DataQualityAnalyzer()

@pytest.fixture
def builder():
    return ProductIdentityBuilder()

@pytest.fixture
def detector():
    return ConflictDetector()


class TestDQSLevel:
    def test_excellent(self):
        assert DQSLevel.from_score(95) == DQSLevel.EXCELLENT
        assert DQSLevel.from_score(90) == DQSLevel.EXCELLENT

    def test_good(self):
        assert DQSLevel.from_score(82) == DQSLevel.GOOD
        assert DQSLevel.from_score(75) == DQSLevel.GOOD

    def test_fair(self):
        assert DQSLevel.from_score(65) == DQSLevel.FAIR
        assert DQSLevel.from_score(60) == DQSLevel.FAIR

    def test_low(self):
        assert DQSLevel.from_score(50) == DQSLevel.LOW
        assert DQSLevel.from_score(40) == DQSLevel.LOW

    def test_very_low(self):
        assert DQSLevel.from_score(30) == DQSLevel.VERY_LOW
        assert DQSLevel.from_score(0) == DQSLevel.VERY_LOW


class TestDQSModel:
    def test_to_dict(self):
        dqs = DataQualityScore(
            overall_score=82.5,
            completeness_score=88.0,
            validity_score=95.0,
            identity_score=90.0,
            attribute_score=75.0,
            source_score=85.0,
            consistency_score=70.0,
            quality_level="GOOD",
        )
        d = dqs.to_dict()
        assert d["overall_score"] == 82.5
        assert d["quality_level"] == "GOOD"
        assert "completeness_score" in d
        assert "validity_score" in d

    def test_score_meaning(self):
        """DQS must NOT contain match/profit/policy language."""
        dqs = DataQualityScore(
            overall_score=95,
            quality_level="EXCELLENT",
            explanation="DATA QUALITY: 95/100 — EXCELLENT",
        )
        assert "match" not in dqs.explanation.lower()
        assert "profit" not in dqs.explanation.lower()
        assert "sell" not in dqs.explanation.lower()
        assert "policy" not in dqs.explanation.lower()


class TestPerfectProduct:
    def test_high_dqs(self, analyzer, builder):
        identity = builder.from_title(
            "Apple iPhone 15 Pro Max 256GB Space Gray New"
        )
        dqs = analyzer.calculate_dqs(identity)
        assert dqs.overall_score >= 60
        assert dqs.quality_level in ("EXCELLENT", "GOOD", "FAIR")

    def test_all_dimensions_populated(self, analyzer, builder):
        identity = builder.from_title("Apple iPhone 15 Pro Max 256GB")
        dqs = analyzer.calculate_dqs(identity)
        assert dqs.completeness_score > 0
        assert dqs.validity_score > 0
        assert dqs.identity_score > 0
        assert dqs.attribute_score > 0
        assert dqs.source_score > 0
        assert dqs.consistency_score > 0


class TestMissingOptionalData:
    def test_missing_condition_small_penalty(self, analyzer, builder):
        with_cond = builder.from_title("iPhone 15 256GB New")
        without_cond = builder.from_title("iPhone 15 256GB")
        dqs_with = analyzer.calculate_dqs(with_cond)
        dqs_without = analyzer.calculate_dqs(without_cond)
        # Missing condition should not cause huge drop
        assert dqs_with.overall_score - dqs_without.overall_score < 20


class TestMissingCoreIdentity:
    def test_missing_product_type_reduces_dqs(self, analyzer, builder):
        identity = builder.from_title("New Hot Sale Best Deal")
        dqs = analyzer.calculate_dqs(identity)
        assert dqs.overall_score < 60
        assert QualityFlag.MISSING_PRODUCT_TYPE.value in dqs.flags

    def test_missing_model_device(self, analyzer, builder):
        identity = builder.from_title("Wireless Bluetooth Earbuds")
        dqs = analyzer.calculate_dqs(identity)
        assert QualityFlag.MISSING_MODEL.value in dqs.flags


class TestUnknownProductType:
    def test_unknown_type_caps_dqs(self, analyzer, builder):
        identity = builder.from_title("Premium Quality Item")
        dqs = analyzer.calculate_dqs(identity)
        assert dqs.overall_score <= 74
        assert len(dqs.caps_applied) > 0


class TestConflictImpact:
    def test_brand_conflict_reduces_consistency(
        self, analyzer, builder, detector
    ):
        a = builder.from_title("Apple iPhone 15")
        b = builder.from_title("Samsung Galaxy S24")
        es = detector.compare(a, b)
        dqs = analyzer.calculate_dqs(a, es)
        assert dqs.consistency_score < 80

    def test_critical_conflict_caps_dqs(
        self, analyzer, builder, detector
    ):
        a = builder.from_title("Apple iPhone 15")
        b = builder.from_title("iPhone 15 Case")
        es = detector.compare(a, b)
        dqs = analyzer.calculate_dqs(a, es)
        assert dqs.overall_score <= 59
        assert len(dqs.caps_applied) > 0


class TestAccessoryQuality:
    def test_accessory_good_quality(self, analyzer, builder):
        identity = builder.from_title("Case for iPhone 15 Pro Max")
        dqs = analyzer.calculate_dqs(identity)
        # Accessory with compatible model should be reasonable
        assert dqs.overall_score >= 40
        assert QualityFlag.ACCESSORY_DEVICE_MISMATCH.value not in dqs.flags

    def test_accessory_not_device_conflict(self, analyzer, builder):
        identity = builder.from_title("Case for iPhone 15 Pro Max")
        dqs = analyzer.calculate_dqs(identity)
        # Compatibility is NOT identity conflict
        assert QualityFlag.CONFLICTING_MODEL.value not in dqs.flags


class TestGenericProduct:
    def test_generic_reasonable_score(self, analyzer, builder):
        identity = builder.from_title("USB Cable 6ft Nylon Braided")
        dqs = analyzer.calculate_dqs(identity)
        # Generic product should not be catastrophic
        assert dqs.overall_score >= 30


class TestAttributeQuality:
    def test_unknown_attribute_penalty(self, analyzer):
        identity = ProductIdentity(
            product_type="earbuds",
            product_role="device",
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="Ocean Mist",
                    status=AttributeStatus.UNKNOWN,
                )
            ],
        )
        dqs = analyzer.calculate_dqs(identity)
        assert QualityFlag.UNKNOWN_ATTRIBUTE.value in dqs.flags

    def test_conflicted_attribute_penalty(self, analyzer):
        identity = ProductIdentity(
            product_type="smartphone",
            product_role="device",
            canonical_attributes=[
                CanonicalAttribute(
                    name="memory", raw_value="16GB",
                    normalized_value="16GB",
                    status=AttributeStatus.CONFLICT,
                    conflict_values=["8GB"],
                )
            ],
        )
        dqs = analyzer.calculate_dqs(identity)
        assert QualityFlag.CONFLICTING_ATTRIBUTE.value in dqs.flags
        assert dqs.attribute_score < 50


class TestSourceQuality:
    def test_api_source_higher(self, analyzer):
        identity_api = ProductIdentity(
            product_type="smartphone",
            product_role="device",
            brand="Apple",
            model="iPhone 15",
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="black",
                    normalized_value="black",
                    source="api",
                    status=AttributeStatus.NORMALIZED,
                )
            ],
            identity_confidence=0.8,
        )
        identity_title = ProductIdentity(
            product_type="smartphone",
            product_role="device",
            brand="Apple",
            model="iPhone 15",
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="black",
                    normalized_value="black",
                    source="title",
                    status=AttributeStatus.NORMALIZED,
                )
            ],
            identity_confidence=0.8,
        )
        dqs_api = analyzer.calculate_dqs(identity_api)
        dqs_title = analyzer.calculate_dqs(identity_title)
        assert dqs_api.source_score >= dqs_title.source_score


class TestDeterminism:
    def test_same_input_same_output(self, analyzer, builder):
        identity = builder.from_title("Apple iPhone 15 Pro Max 256GB")
        dqs1 = analyzer.calculate_dqs(identity).to_dict()
        dqs2 = analyzer.calculate_dqs(identity).to_dict()
        assert dqs1 == dqs2

    def test_deterministic_100_times(self, analyzer, builder):
        identity = builder.from_title("Samsung Galaxy S24 Ultra 512GB")
        results = [
            analyzer.calculate_dqs(identity).overall_score
            for _ in range(100)
        ]
        assert len(set(results)) == 1


class TestScoreBreakdown:
    def test_breakdown_complete(self, analyzer, builder):
        identity = builder.from_title("Apple iPhone 15 256GB Black")
        dqs = analyzer.calculate_dqs(identity)
        d = dqs.to_dict()
        required = [
            "overall_score", "completeness_score", "validity_score",
            "identity_score", "attribute_score", "source_score",
            "consistency_score", "quality_level", "strengths",
            "limitations", "flags", "explanation", "caps_applied",
        ]
        for key in required:
            assert key in d, f"Missing: {key}"


class TestNoMatchScore:
    def test_no_match_language(self, analyzer, builder):
        identity = builder.from_title("Apple iPhone 15")
        dqs = analyzer.calculate_dqs(identity)
        import json
        serialized = json.dumps(dqs.to_dict())
        assert "match_score" not in serialized
        assert "match_probability" not in serialized
        assert "sell_probability" not in serialized
        assert "profit" not in serialized.lower()


class TestPolicySeparation:
    def test_no_policy_in_dqs(self, analyzer, builder):
        identity = builder.from_title("Apple iPhone 15")
        dqs = analyzer.calculate_dqs(identity)
        assert "policy" not in dqs.explanation.lower()
        assert "prohibited" not in dqs.explanation.lower()


class TestExplanation:
    def test_explanation_factual(self, analyzer, builder):
        identity = builder.from_title("Apple iPhone 15 256GB")
        dqs = analyzer.calculate_dqs(identity)
        assert "DATA QUALITY" in dqs.explanation
        assert len(dqs.explanation) > 10

    def test_explanation_no_profit(self, analyzer, builder):
        identity = builder.from_title("Apple iPhone 15")
        dqs = analyzer.calculate_dqs(identity)
        assert "profitable" not in dqs.explanation.lower()
        assert "strong match" not in dqs.explanation.lower()