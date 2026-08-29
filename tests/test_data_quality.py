"""Tests for Data Quality & Confidence Layer."""
import pytest
from services.product_identity import (
    ProductIdentityBuilder,
    ConflictDetector,
    DataQualityAnalyzer,
    ConfidenceLevel,
    FieldConfidence,
    DataQualityReport,
    QualityFlag,
)
from services.product_identity.models import ProductIdentity
from services.product_identity.attributes import (
    CanonicalAttribute,
    AttributeStatus,
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


class TestConfidenceLevel:
    def test_four_levels(self):
        assert ConfidenceLevel.HIGH.score == 0.9
        assert ConfidenceLevel.MEDIUM.score == 0.6
        assert ConfidenceLevel.LOW.score == 0.3
        assert ConfidenceLevel.UNKNOWN.score == 0.0

    def test_scores_ordered(self):
        assert (
            ConfidenceLevel.HIGH.score
            > ConfidenceLevel.MEDIUM.score
            > ConfidenceLevel.LOW.score
            > ConfidenceLevel.UNKNOWN.score
        )


class TestFieldConfidence:
    def test_to_dict(self):
        fc = FieldConfidence(
            field="brand",
            confidence=ConfidenceLevel.HIGH,
            source="brand_detector",
            reason="Brand matched.",
        )
        d = fc.to_dict()
        assert d["field"] == "brand"
        assert d["confidence"] == "high"
        assert d["score"] == 0.9
        assert d["source"] == "brand_detector"


class TestDataQualityReport:
    def test_empty_report(self):
        r = DataQualityReport()
        assert r.completeness == 0.0
        assert r.consistency == 0.0
        assert r.overall_quality == "LOW"
        assert not r.has_critical_issues

    def test_critical_issues(self):
        r = DataQualityReport(
            flags=[QualityFlag.MISSING_PRODUCT_TYPE.value]
        )
        assert r.has_critical_issues

    def test_conflict_flags(self):
        r = DataQualityReport(
            flags=[
                QualityFlag.CONFLICTING_BRAND.value,
                QualityFlag.MISSING_BRAND.value,
            ]
        )
        assert len(r.conflict_flags) == 1
        assert len(r.missing_flags) == 1

    def test_to_dict(self):
        r = DataQualityReport(
            completeness=0.7,
            consistency=0.9,
            source_quality=0.8,
            overall_quality="HIGH",
        )
        d = r.to_dict()
        assert d["completeness"] == 0.7
        assert d["overall_quality"] == "HIGH"


class TestHighQualityProduct:
    def test_structured_product_high_quality(self, analyzer, builder):
        identity = builder.from_title(
            "Apple iPhone 15 Pro Max 256GB Space Gray"
        )
        report = analyzer.analyze(identity)
        assert report.overall_quality in ("HIGH", "MEDIUM")
        assert report.completeness >= 0.4
        assert report.consistency >= 0.8

    def test_field_confidences_populated(self, analyzer, builder):
        identity = builder.from_title(
            "Apple iPhone 15 Pro Max 256GB Black"
        )
        report = analyzer.analyze(identity)
        assert len(report.field_confidences) > 0
        fields = {fc.field for fc in report.field_confidences}
        assert "product_type" in fields
        assert "brand" in fields
        assert "model" in fields


class TestLowQualityProduct:
    def test_generic_product_low_quality(self, analyzer, builder):
        identity = builder.from_title("New Hot Sale Best Deal")
        report = analyzer.analyze(identity)
        assert report.overall_quality == "LOW"
        assert report.completeness < 0.4

    def test_missing_model_flag(self, analyzer, builder):
        identity = builder.from_title("Wireless Earbuds Bluetooth")
        report = analyzer.analyze(identity)
        assert QualityFlag.MISSING_MODEL.value in report.flags

    def test_missing_brand_flag(self, analyzer, builder):
        identity = builder.from_title("Wireless Earbuds Bluetooth")
        report = analyzer.analyze(identity)
        assert QualityFlag.MISSING_BRAND.value in report.flags


class TestBrandConfidence:
    def test_known_brand_high_confidence(self, analyzer, builder):
        identity = builder.from_title("Apple iPhone 15")
        report = analyzer.analyze(identity)
        brand_fc = [
            fc for fc in report.field_confidences
            if fc.field == "brand"
        ]
        assert len(brand_fc) > 0
        assert brand_fc[0].confidence == ConfidenceLevel.HIGH

    def test_missing_brand_unknown(self, analyzer, builder):
        identity = builder.from_title("Wireless Earbuds")
        report = analyzer.analyze(identity)
        brand_fc = [
            fc for fc in report.field_confidences
            if fc.field == "brand"
        ]
        assert len(brand_fc) > 0
        assert brand_fc[0].confidence == ConfidenceLevel.UNKNOWN


class TestModelConfidence:
    def test_explicit_model_high(self, analyzer, builder):
        identity = builder.from_title("Sony WH-1000XM5 Headphones")
        report = analyzer.analyze(identity)
        model_fc = [
            fc for fc in report.field_confidences
            if fc.field == "model"
        ]
        assert len(model_fc) > 0
        assert model_fc[0].confidence == ConfidenceLevel.HIGH

    def test_no_model_unknown(self, analyzer, builder):
        identity = builder.from_title("Wireless Earbuds")
        report = analyzer.analyze(identity)
        model_fc = [
            fc for fc in report.field_confidences
            if fc.field == "model"
        ]
        assert len(model_fc) > 0
        assert model_fc[0].confidence == ConfidenceLevel.UNKNOWN


class TestAttributeConfidence:
    def test_normalized_attribute_high(self, analyzer, builder):
        identity = builder.from_title("iPhone 15 256GB Black")
        report = analyzer.analyze(identity)
        storage_fc = [
            fc for fc in report.field_confidences
            if fc.field == "storage"
        ]
        assert len(storage_fc) > 0
        assert storage_fc[0].confidence in (
            ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM
        )

    def test_unknown_attribute_low(self, analyzer):
        identity = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="color",
                    raw_value="Ocean Mist",
                    normalized_value=None,
                    status=AttributeStatus.UNKNOWN,
                )
            ]
        )
        report = analyzer.analyze(identity)
        color_fc = [
            fc for fc in report.field_confidences
            if fc.field == "color"
        ]
        assert len(color_fc) > 0
        assert color_fc[0].confidence == ConfidenceLevel.LOW

    def test_conflicting_attribute_low(self, analyzer):
        identity = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="memory",
                    raw_value="16GB",
                    normalized_value="16GB",
                    status=AttributeStatus.CONFLICT,
                    conflict_values=["8GB"],
                )
            ]
        )
        report = analyzer.analyze(identity)
        mem_fc = [
            fc for fc in report.field_confidences
            if fc.field == "memory"
        ]
        assert len(mem_fc) > 0
        assert mem_fc[0].confidence == ConfidenceLevel.LOW
        assert QualityFlag.CONFLICTING_ATTRIBUTE.value in report.flags


class TestConsistencyWithEvidence:
    def test_no_conflicts_high_consistency(
        self, analyzer, builder, detector
    ):
        a = builder.from_title("Apple iPhone 15 256GB Black")
        b = builder.from_title("Apple iPhone 15 256GB Black")
        es = detector.compare(a, b)
        report = analyzer.analyze(a, es)
        assert report.consistency >= 0.8

    def test_critical_conflict_low_consistency(
        self, analyzer, builder, detector
    ):
        a = builder.from_title("Apple iPhone 15")
        b = builder.from_title("Samsung Galaxy S24")
        es = detector.compare(a, b)
        report = analyzer.analyze(a, es)
        assert report.consistency < 0.8

    def test_brand_conflict_flag(
        self, analyzer, builder, detector
    ):
        a = builder.from_title("Apple iPhone 15")
        b = builder.from_title("Samsung Galaxy S24")
        es = detector.compare(a, b)
        report = analyzer.analyze(a, es)
        assert QualityFlag.CONFLICTING_BRAND.value in report.flags


class TestMissingVsUnknown:
    def test_missing_not_conflict(self, analyzer, builder):
        identity = builder.from_title("Wireless Earbuds Bluetooth")
        report = analyzer.analyze(identity)
        # Brand is missing, not conflicting
        assert QualityFlag.MISSING_BRAND.value in report.flags
        assert QualityFlag.CONFLICTING_BRAND.value not in report.flags

    def test_unknown_distinct_from_missing(self, analyzer):
        identity = ProductIdentity(
            product_type="earbuds",
            canonical_attributes=[
                CanonicalAttribute(
                    name="color",
                    raw_value="Ocean Mist",
                    status=AttributeStatus.UNKNOWN,
                )
            ],
        )
        report = analyzer.analyze(identity)
        assert QualityFlag.UNKNOWN_ATTRIBUTE.value in report.flags
        # Missing brand is different from unknown color
        assert QualityFlag.MISSING_BRAND.value in report.flags


class TestCompleteness:
    def test_full_identity_high_completeness(self, analyzer, builder):
        identity = builder.from_title(
            "Apple iPhone 15 Pro Max 256GB Space Gray New"
        )
        report = analyzer.analyze(identity)
        assert report.completeness >= 0.5

    def test_minimal_identity_low_completeness(self, analyzer, builder):
        identity = builder.from_title("Thing")
        report = analyzer.analyze(identity)
        assert report.completeness < 0.3


class TestSourceQuality:
    def test_api_source_high(self, analyzer):
        identity = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="color",
                    raw_value="black",
                    normalized_value="black",
                    source="api",
                    status=AttributeStatus.NORMALIZED,
                )
            ]
        )
        report = analyzer.analyze(identity)
        assert report.source_quality >= 0.7

    def test_title_source_medium(self, analyzer, builder):
        identity = builder.from_title("Wireless Earbuds Black")
        report = analyzer.analyze(identity)
        assert report.source_quality >= 0.5


class TestDeterminism:
    def test_same_input_same_output(self, analyzer, builder):
        identity = builder.from_title(
            "Apple iPhone 15 Pro Max 256GB Black"
        )
        r1 = analyzer.analyze(identity).to_dict()
        r2 = analyzer.analyze(identity).to_dict()
        assert r1 == r2


class TestExplanation:
    def test_explanation_not_empty(self, analyzer, builder):
        identity = builder.from_title("Apple iPhone 15")
        report = analyzer.analyze(identity)
        assert len(report.explanation) > 0
        assert "DATA QUALITY" in report.explanation

    def test_explanation_factual(self, analyzer, builder):
        identity = builder.from_title("Apple iPhone 15")
        report = analyzer.analyze(identity)
        assert "match score" not in report.explanation.lower()
        assert "profit" not in report.explanation.lower()
        assert "sell" not in report.explanation.lower()


class TestNoMatchScore:
    def test_report_has_no_match_score(self, analyzer, builder):
        identity = builder.from_title("Apple iPhone 15")
        report = analyzer.analyze(identity)
        import json
        serialized = json.dumps(report.to_dict())
        assert "match_score" not in serialized
        assert "match_probability" not in serialized
        assert "sell_probability" not in serialized


class TestPolicySeparation:
    def test_quality_independent_of_policy(self, analyzer, builder):
        """Data quality and policy risk are independent."""
        identity = builder.from_title(
            "Apple iPhone 15 Pro Max 256GB"
        )
        report = analyzer.analyze(identity)
        # Quality report should not mention policy
        assert "policy" not in report.explanation.lower()
        assert "prohibited" not in report.explanation.lower()
        assert "restricted" not in report.explanation.lower()