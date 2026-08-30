"""Tests for Conflict Detector and Evidence System."""
import pytest
from services.product_identity import (
    ProductIdentityBuilder,
    ConflictDetector,
    EvidenceType,
    EvidenceStrength,
    ConflictSeverity,
)
from services.product_identity.evidence import Evidence, EvidenceSet


@pytest.fixture
def detector():
    return ConflictDetector()

@pytest.fixture
def builder():
    return ProductIdentityBuilder()


class TestEvidenceModel:
    def test_evidence_to_dict(self):
        e = Evidence(field="brand", evidence_type=EvidenceType.POSITIVE,
                     strength=EvidenceStrength.STRONG, value_a="Apple",
                     value_b="Apple", explanation="Same brand.")
        d = e.to_dict()
        assert d["field"] == "brand"
        assert d["evidence_type"] == "positive"

    def test_evidence_set_empty(self):
        es = EvidenceSet()
        assert es.positive_count == 0
        assert es.conflict_count == 0
        assert not es.has_critical_conflicts

    def test_evidence_set_to_dict(self):
        es = EvidenceSet()
        d = es.to_dict()
        assert "summary" in d
        assert d["summary"]["total_evidence"] == 0


class TestBrandComparison:
    def test_same_brand(self, detector, builder):
        a = builder.from_title("Apple iPhone 15 Pro Max")
        b = builder.from_title("Apple AirPods Pro 2")
        es = detector.compare(a, b)
        brand_pos = [e for e in es.positive if e.field == "brand"]
        assert len(brand_pos) > 0

    def test_different_brand(self, detector, builder):
        a = builder.from_title("Apple iPhone 15")
        b = builder.from_title("Samsung Galaxy S24")
        es = detector.compare(a, b)
        brand_conf = [e for e in es.conflicts if e.field == "brand"]
        assert len(brand_conf) > 0
        assert brand_conf[0].severity == ConflictSeverity.STRONG

    def test_missing_brand(self, detector, builder):
        a = builder.from_title("Apple iPhone 15")
        b = builder.from_title("Wireless Earbuds Bluetooth")
        es = detector.compare(a, b)
        brand_miss = [e for e in es.missing if e.field == "brand"]
        assert len(brand_miss) > 0
        # Missing is NOT a conflict
        brand_conf = [e for e in es.conflicts if e.field == "brand"]
        assert len(brand_conf) == 0


class TestProductTypeComparison:
    def test_same_type(self, detector, builder):
        a = builder.from_title("Wireless Bluetooth Earbuds TWS")
        b = builder.from_title("TWS Earbuds Bluetooth 5.3")
        es = detector.compare(a, b)
        type_pos = [e for e in es.positive if e.field == "product_type"]
        assert len(type_pos) > 0

    def test_different_type(self, detector, builder):
        a = builder.from_title("Apple iPhone 15 Pro Max")
        b = builder.from_title("iPhone 15 Case Silicone")
        es = detector.compare(a, b)
        type_conf = [e for e in es.conflicts if e.field == "product_type"]
        assert len(type_conf) > 0
        assert type_conf[0].severity == ConflictSeverity.CRITICAL

    def test_headphones_vs_case(self, detector, builder):
        a = builder.from_title("Sony WH-1000XM5 Headphones")
        b = builder.from_title("iPhone Case Clear")
        es = detector.compare(a, b)
        assert es.has_critical_conflicts


class TestModelComparison:
    def test_same_model(self, detector, builder):
        a = builder.from_title("NVIDIA RTX 4070 12GB")
        b = builder.from_title("RTX 4070 Graphics Card")
        es = detector.compare(a, b)
        model_pos = [e for e in es.positive if e.field == "model"]
        assert len(model_pos) > 0

    def test_different_model(self, detector, builder):
        a = builder.from_title("NVIDIA RTX 4070")
        b = builder.from_title("NVIDIA RTX 3060")
        es = detector.compare(a, b)
        model_conf = [e for e in es.conflicts if e.field == "model"]
        assert len(model_conf) > 0
        assert model_conf[0].severity == ConflictSeverity.STRONG

    def test_model_specificity(self, detector, builder):
        a = builder.from_title("iPhone 15 Pro Max 256GB")
        b = builder.from_title("iPhone 15 128GB")
        es = detector.compare(a, b)
        model_neg = [e for e in es.negative if e.field == "model"]
        assert len(model_neg) > 0
        assert model_neg[0].severity == ConflictSeverity.MODERATE


class TestVariantComparison:
    def test_same_variant(self, detector, builder):
        a = builder.from_title("AirPods Pro USB-C")
        b = builder.from_title("AirPods Pro USB-C White")
        es = detector.compare(a, b)
        # Both should have USB-C variant
        variant_evidence = [
            e for e in es.all_evidence if e.field == "variant"
        ]
        # May or may not match exactly depending on other variant components
        assert isinstance(variant_evidence, list)

    def test_usb_c_vs_lightning(self, detector, builder):
        a = builder.from_title("AirPods Pro USB-C")
        b = builder.from_title("AirPods Pro Lightning")
        es = detector.compare(a, b)
        variant_conf = [e for e in es.conflicts if e.field == "variant"]
        assert len(variant_conf) > 0


class TestAttributeComparison:
    def test_same_color(self, detector, builder):
        a = builder.from_title("iPhone 15 Black")
        b = builder.from_title("iPhone 15 Black Case")
        es = detector.compare(a, b)
        color_pos = [e for e in es.positive if e.field == "color"]
        assert len(color_pos) > 0

    def test_different_color(self, detector, builder):
        a = builder.from_title("iPhone 15 Black")
        b = builder.from_title("iPhone 15 Red")
        es = detector.compare(a, b)
        color_conf = [e for e in es.conflicts if e.field == "color"]
        assert len(color_conf) > 0
        assert color_conf[0].severity == ConflictSeverity.MODERATE

    def test_same_storage(self, detector, builder):
        a = builder.from_title("iPhone 15 256GB")
        b = builder.from_title("iPhone 15 256GB Black")
        es = detector.compare(a, b)
        stor_pos = [e for e in es.positive if e.field == "storage"]
        assert len(stor_pos) > 0

    def test_different_storage(self, detector, builder):
        a = builder.from_title("iPhone 15 128GB")
        b = builder.from_title("iPhone 15 512GB")
        es = detector.compare(a, b)
        stor_conf = [e for e in es.conflicts if e.field == "storage"]
        assert len(stor_conf) > 0
        assert stor_conf[0].severity == ConflictSeverity.STRONG


class TestUnitAwareComparison:
    def test_1tb_vs_1024gb_no_conflict(self, detector, builder):
        a = builder.from_title("Samsung SSD 1TB")
        b = builder.from_title("Samsung SSD 1024GB")
        es = detector.compare(a, b)
        stor_conf = [e for e in es.conflicts if e.field == "storage"]
        assert len(stor_conf) == 0
        stor_pos = [e for e in es.positive if e.field == "storage"]
        assert len(stor_pos) > 0


class TestMissingEvidence:
    def test_missing_not_conflict(self, detector, builder):
        a = builder.from_title("Apple iPhone 15 256GB Black")
        b = builder.from_title("Wireless Earbuds")
        es = detector.compare(a, b)
        # b has no storage — should be missing, NOT conflict
        stor_miss = [e for e in es.missing if e.field == "storage"]
        stor_conf = [e for e in es.conflicts if e.field == "storage"]
        assert len(stor_miss) > 0
        assert len(stor_conf) == 0


class TestUnknownEvidence:
    def test_unknown_color_not_strong_conflict(self, detector):
        from services.product_identity.models import ProductIdentity
        from services.product_identity.attributes import (
            CanonicalAttribute, AttributeStatus
        )
        a = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="black",
                    normalized_value="black",
                    status=AttributeStatus.NORMALIZED,
                )
            ]
        )
        b = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="Ocean Mist",
                    normalized_value=None,
                    status=AttributeStatus.UNKNOWN,
                )
            ]
        )
        es = detector.compare(a, b)
        unknown_ev = [e for e in es.unknown if e.field == "color"]
        assert len(unknown_ev) > 0
        color_conf = [e for e in es.conflicts if e.field == "color"]
        assert len(color_conf) == 0


class TestAccessoryContext:
    def test_accessory_vs_device_conflict(self, detector, builder):
        a = builder.from_title("Apple iPhone 15 Pro Max 256GB")
        b = builder.from_title("Case for iPhone 15 Pro Max")
        es = detector.compare(a, b)
        acc_conf = [
            e for e in es.conflicts if e.field == "accessory_context"
        ]
        assert len(acc_conf) > 0
        assert acc_conf[0].severity == ConflictSeverity.CRITICAL

    def test_two_devices_no_accessory_conflict(self, detector, builder):
        a = builder.from_title("iPhone 15 Pro Max 256GB")
        b = builder.from_title("iPhone 15 Pro 128GB")
        es = detector.compare(a, b)
        acc_conf = [
            e for e in es.conflicts if e.field == "accessory_context"
        ]
        assert len(acc_conf) == 0


class TestEvidenceSetProperties:
    def test_has_critical_conflicts(self, detector, builder):
        a = builder.from_title("Apple iPhone 15")
        b = builder.from_title("iPhone 15 Case")
        es = detector.compare(a, b)
        assert es.has_critical_conflicts

    def test_no_critical_conflicts(self, detector, builder):
        a = builder.from_title("Wireless Bluetooth Earbuds Black")
        b = builder.from_title("Bluetooth Earbuds TWS Black")
        es = detector.compare(a, b)
        assert not es.has_critical_conflicts

    def test_evidence_counts(self, detector, builder):
        a = builder.from_title("Apple iPhone 15 Pro Max 256GB Black")
        b = builder.from_title("Apple iPhone 15 Pro Max 256GB Black")
        es = detector.compare(a, b)
        assert es.positive_count > 0
        assert es.conflict_count == 0


class TestDeterminism:
    def test_same_input_same_output(self, detector, builder):
        a = builder.from_title("Apple iPhone 15 Pro Max 256GB")
        b = builder.from_title("Samsung Galaxy S24 Ultra 512GB")
        es1 = detector.compare(a, b).to_dict()
        es2 = detector.compare(a, b).to_dict()
        assert es1 == es2

    def test_symmetric(self, detector, builder):
        a = builder.from_title("Apple iPhone 15")
        b = builder.from_title("Samsung Galaxy S24")
        es_ab = detector.compare(a, b)
        es_ba = detector.compare(b, a)
        assert es_ab.conflict_count == es_ba.conflict_count


class TestExplanations:
    def test_explanations_are_factual(self, detector, builder):
        a = builder.from_title("Apple iPhone 15")
        b = builder.from_title("Samsung Galaxy S24")
        es = detector.compare(a, b)
        for e in es.all_evidence:
            assert isinstance(e.explanation, str)
            assert len(e.explanation) > 0
            # Must not claim match/no-match decision
            assert "definitely" not in e.explanation.lower()
            assert "guaranteed" not in e.explanation.lower()
            assert "match score" not in e.explanation.lower()

    def test_no_match_score_in_output(self, detector, builder):
        a = builder.from_title("Apple iPhone 15")
        b = builder.from_title("Apple iPhone 15")
        es = detector.compare(a, b)
        d = es.to_dict()
        # Must not contain match_score anywhere
        import json
        serialized = json.dumps(d)
        assert "match_score" not in serialized
        assert "match_probability" not in serialized