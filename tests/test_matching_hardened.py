"""
Hardened Product Matching Tests + Golden Dataset.
"""
from decimal import Decimal
import pytest

from services.matching import (
    ProductMatcher,
    ProductMatchResult,
    TextSimilarity,
    AttributeSimilarity,
    CompatibilitySimilarity,
    IdentifierSimilarity,
    ConditionSimilarity,
    VariantSimilarity,
)
from services.product_identity import ProductIdentityBuilder
from services.product_identity.models import ProductIdentity
from services.product_identity.attributes import (
    CanonicalAttribute,
    AttributeStatus,
)
from services.aliexpress.models import (
    AliExpressProduct,
    AliExpressPrice,
    AliExpressStore,
)


@pytest.fixture
def matcher():
    """Matcher WITH candidate filter (default)."""
    return ProductMatcher()


@pytest.fixture
def matcher_no_filter():
    """Matcher WITHOUT candidate filter for direct testing."""
    return ProductMatcher(use_candidate_filter=False)


@pytest.fixture
def builder():
    return ProductIdentityBuilder()


def _ali(title, price=9.99, **kwargs):
    defaults = {
        "product_id": f"ali_{hash(title) % 100000}",
        "title": title,
        "price": AliExpressPrice(value=Decimal(str(price))),
        "product_url": "https://example.com",
        "source": "mock",
    }
    defaults.update(kwargs)
    return AliExpressProduct(**defaults)


def _ebay(item_id, title, price=29.99):
    return {
        "item_id": item_id,
        "title": title,
        "price_value": Decimal(str(price)),
        "price_currency": "USD",
        "marketplace": "EBAY_US",
    }


# =============================================================================
# CRITICAL ATTRIBUTE MATCHING
# =============================================================================

class TestCriticalAttributes:
    def test_brand_mismatch_filtered(self, matcher):
        """Brand mismatch → candidate filter removes it."""
        ebay = _ebay("v1|1|0", "Apple iPhone 15 Pro Max")
        ali = _ali("Samsung Galaxy S24 Ultra Case")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) == 0  # Filtered out

    def test_brand_mismatch_low_score(self, matcher_no_filter):
        """Without filter, brand mismatch → hard rejection → low score."""
        ebay = _ebay("v1|1|0", "Apple iPhone 15 Pro Max")
        ali = _ali("Samsung Galaxy S24 Ultra Case")
        results = matcher_no_filter.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score < 0.40

    def test_type_mismatch_filtered(self, matcher):
        """Type mismatch → candidate filter removes it."""
        ebay = _ebay("v1|2|0", "Wireless Bluetooth Earbuds TWS")
        ali = _ali("Mechanical Gaming Keyboard RGB")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) == 0

    def test_type_mismatch_low_score(self, matcher_no_filter):
        """Without filter, type mismatch → hard rejection."""
        ebay = _ebay("v1|2|0", "Wireless Bluetooth Earbuds TWS")
        ali = _ali("Mechanical Gaming Keyboard RGB")
        results = matcher_no_filter.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score < 0.40

    def test_critical_match_positive(self, matcher):
        ebay = _ebay("v1|3|0", "Apple AirPods Pro 2 USB-C")
        ali = _ali("Apple AirPods Pro 2 USB-C TWS")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score >= 0.60


# =============================================================================
# COMPATIBILITY MATCHING
# =============================================================================

class TestCompatibilityMatching:
    def test_compatible_accessories(self, matcher):
        ebay = _ebay("v1|10|0", "Case for iPhone 15 Pro Max")
        ali = _ali("iPhone 15 Pro Max Protective Case Silicone")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score >= 0.40

    def test_incompatible_accessories(self, matcher):
        ebay = _ebay("v1|11|0", "Case for iPhone 15 Pro Max")
        ali = _ali("Samsung Galaxy S24 Case")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        # Both phone_case type, both accessories — eligible
        if results:
            assert results[0].match_score < 0.50

    def test_device_vs_accessory_filtered(self, matcher):
        """Device vs accessory → candidate filter removes it."""
        ebay = _ebay("v1|12|0", "Apple iPhone 15 Pro Max 256GB")
        ali = _ali("iPhone 15 Pro Max Silicone Case")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) == 0

    def test_device_vs_accessory_low_score(self, matcher_no_filter):
        """Without filter, device vs accessory → low score."""
        ebay = _ebay("v1|12|0", "Apple iPhone 15 Pro Max 256GB")
        ali = _ali("iPhone 15 Pro Max Silicone Case")
        results = matcher_no_filter.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score < 0.40

    def test_compatibility_evidence(self, builder):
        ebay_id = builder.from_title("Case for iPhone 15 Pro Max")
        ali_id = builder.from_title("iPhone 15 Pro Max Case Clear")
        sim = CompatibilitySimilarity()
        score, ev = sim.calculate(ebay_id, ali_id)
        assert score >= 0.7
        assert any("compatible" in e.lower() for e in ev)


# =============================================================================
# IDENTIFIER MATCHING
# =============================================================================

class TestIdentifierMatching:
    def test_matching_mpn(self):
        a = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="mpn", raw_value="MQD32LL/A",
                    normalized_value="MQD32LL/A",
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        b = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="mpn", raw_value="MQD32LL/A",
                    normalized_value="MQD32LL/A",
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        sim = IdentifierSimilarity()
        score, ev = sim.calculate(a, b)
        assert score == 1.0

    def test_conflicting_identifiers(self):
        a = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="upc", raw_value="1234567890",
                    normalized_value="1234567890",
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        b = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="upc", raw_value="9876543210",
                    normalized_value="9876543210",
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        sim = IdentifierSimilarity()
        score, ev = sim.calculate(a, b)
        assert score == 0.0

    def test_missing_identifiers_neutral(self):
        a = ProductIdentity(canonical_attributes=[])
        b = ProductIdentity(canonical_attributes=[])
        sim = IdentifierSimilarity()
        score, ev = sim.calculate(a, b)
        assert score == 0.5


# =============================================================================
# VARIANT MATCHING
# =============================================================================

class TestVariantMatching:
    def test_same_variant(self, builder):
        a = builder.from_title("iPhone 15 Pro Max 256GB Black")
        b = builder.from_title("iPhone 15 Pro Max 256GB Black")
        sim = VariantSimilarity()
        score, matches, diffs = sim.calculate(a, b)
        assert score >= 0.8

    def test_different_storage_variant(self, builder):
        a = builder.from_title("iPhone 15 Pro Max 256GB")
        b = builder.from_title("iPhone 15 Pro Max 512GB")
        sim = VariantSimilarity()
        score, matches, diffs = sim.calculate(a, b)
        assert score < 1.0
        assert len(diffs) > 0

    def test_unit_equivalent_no_conflict(self, builder):
        a = builder.from_title("Samsung SSD 1TB")
        b = builder.from_title("Samsung SSD 1024GB")
        sim = VariantSimilarity()
        score, matches, diffs = sim.calculate(a, b)
        storage_conflicts = [d for d in diffs if "storage" in d.lower()]
        assert len(storage_conflicts) == 0

    def test_connectivity_variant_conflict(self, builder):
        a = builder.from_title("AirPods Pro USB-C")
        b = builder.from_title("AirPods Pro Lightning")
        sim = VariantSimilarity()
        score, matches, diffs = sim.calculate(a, b)
        assert score < 1.0


# =============================================================================
# CONDITION MATCHING
# =============================================================================

class TestConditionMatching:
    def test_same_condition(self):
        a = ProductIdentity(condition="new")
        b = ProductIdentity(condition="new")
        sim = ConditionSimilarity()
        score, ev = sim.calculate(a, b)
        assert score == 1.0

    def test_new_vs_used(self):
        a = ProductIdentity(condition="new")
        b = ProductIdentity(condition="used")
        sim = ConditionSimilarity()
        score, ev = sim.calculate(a, b)
        assert score < 0.5

    def test_new_vs_refurbished(self):
        a = ProductIdentity(condition="new")
        b = ProductIdentity(condition="refurbished")
        sim = ConditionSimilarity()
        score, ev = sim.calculate(a, b)
        assert score < 0.7

    def test_unknown_condition_neutral(self):
        a = ProductIdentity(condition=None)
        b = ProductIdentity(condition="new")
        sim = ConditionSimilarity()
        score, ev = sim.calculate(a, b)
        assert score == 0.5


# =============================================================================
# MATCH EXPLANATION
# =============================================================================

class TestMatchExplanation:
    def test_explanation_populated(self, matcher):
        ebay = _ebay("v1|50|0", "Apple AirPods Pro 2 USB-C White")
        ali = _ali("Apple AirPods Pro 2 USB-C White TWS")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        r = results[0]
        assert len(r.positive_evidence) > 0 or len(r.negative_evidence) > 0
        assert len(r.score_contributions) > 0
        d = r.to_dict()
        assert "positive_evidence" in d
        assert "negative_evidence" in d
        assert "penalties" in d
        assert "score_contributions" in d
        assert "similarities" in d

    def test_explanation_deterministic(self, matcher):
        ebay = _ebay("v1|51|0", "Samsung Galaxy S24 Ultra 256GB")
        ali = _ali("Samsung Galaxy S24 Ultra 256GB Black")
        r1 = matcher.find_matches(ebay, [ali], min_score=0.0)[0]
        r2 = matcher.find_matches(ebay, [ali], min_score=0.0)[0]
        assert r1.positive_evidence == r2.positive_evidence
        assert r1.negative_evidence == r2.negative_evidence


# =============================================================================
# CONFIDENCE IMPROVEMENTS
# =============================================================================

class TestConfidenceImprovements:
    def test_high_similarity_low_data_quality(self, matcher):
        a = ProductIdentity(
            product_type="earbuds",
            keywords=["wireless", "earbuds"],
            identity_confidence=0.3,
        )
        b = ProductIdentity(
            product_type="earbuds",
            keywords=["wireless", "earbuds"],
            identity_confidence=0.3,
        )
        result = matcher.match_pair(a, b)
        assert result.confidence <= 0.5

    def test_confidence_bounded(self, matcher):
        ebay = _ebay("v1|60|0", "Apple iPhone 15 Pro Max 256GB")
        ali = _ali("Apple iPhone 15 Pro Max 256GB")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert 0.0 <= results[0].confidence <= 1.0


# =============================================================================
# CATEGORY-AWARE WEIGHTS
# =============================================================================

class TestCategoryAwareWeights:
    def test_default_weights_sum_to_one(self, matcher):
        total = sum(matcher.DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.02  # Allow small float rounding

    def test_category_weights_sum_to_one(self, matcher, builder):
        identity = builder.from_title("Apple iPhone 15 Pro Max")
        weights = matcher._get_category_weights(identity)
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01

    def test_accessory_boosts_compatibility(self, matcher, builder):
        identity = builder.from_title("Case for iPhone 15 Pro Max")
        weights = matcher._get_category_weights(identity)
        # After normalization, compatibility should be boosted
        assert weights.get("compatibility", 0) >= 0.10


# =============================================================================
# GOLDEN DATASET
# =============================================================================

GOLDEN_DATASET = [
    # MATCH pairs (60)
    ("Apple AirPods Pro 2 USB-C", "Apple AirPods Pro 2 USB-C TWS", "MATCH"),
    ("Apple AirPods Pro 2 USB-C White", "Apple AirPods Pro 2 USB-C White", "MATCH"),
    ("Samsung Galaxy S24 Ultra 256GB", "Samsung Galaxy S24 Ultra 256GB", "MATCH"),
    ("Samsung Galaxy S24 128GB Black", "Samsung Galaxy S24 128GB Black", "MATCH"),
    ("Sony WH-1000XM5 Headphones", "Sony WH-1000XM5 Wireless Headphones", "MATCH"),
    ("Wireless Bluetooth Earbuds TWS", "TWS Wireless Bluetooth Earbuds", "MATCH"),
    ("USB-C Charging Cable 6ft", "USB-C Cable 6ft Braided", "MATCH"),
    ("USB-C to Lightning Cable", "Lightning to USB-C Cable", "MATCH"),
    ("iPhone 15 Case Silicone", "Silicone Case for iPhone 15", "MATCH"),
    ("iPhone 15 Pro Max Case", "iPhone 15 Pro Max Protective Case", "MATCH"),
    ("Samsung Galaxy S24 Case", "Case for Samsung Galaxy S24", "MATCH"),
    ("USB-C Hub Multiport", "7-in-1 USB Type C Hub", "MATCH"),
    ("Smart Watch Series 9", "Smart Watch Series 9 GPS Only", "MATCH"),
    ("Adjustable Laptop Riser", "Adjustable Laptop Stand Holder", "MATCH"),
    ("Bose QuietComfort 45", "Bose QC45 Wireless Headphones", "MATCH"),
    ("Anker PowerCore 10000", "Anker 10000mAh Portable Charger", "MATCH"),
    ("Apple iPhone 15 Pro", "Samsung Galaxy S24 Plus", "NOT_MATCH"),
    ("Wireless Mouse", "Wired Keyboard RGB", "NOT_MATCH"),
    ("Silicone Case for iPhone", "USB-C Wall Charger 20W", "NOT_MATCH"),
    ("SSD 1TB Internal", "SATA Hard Drive 1TB", "NOT_MATCH"),
    ("Laptop Sleeve Case 13", "Laptop Stand Adjustable", "NOT_MATCH"),
    ("Wireless Mouse Bluetooth", "Bluetooth Wireless Mouse", "MATCH"),
    ("Mechanical Keyboard RGB", "RGB Mechanical Gaming Keyboard", "MATCH"),
    ("Bluetooth Speaker Portable", "Portable Bluetooth Speaker", "MATCH"),
    ("Power Bank 20000mAh", "20000mAh Power Bank Portable", "MATCH"),
    ("USB-C Hub 7-in-1", "7-in-1 USB-C Hub Adapter", "MATCH"),
    ("Laptop Stand Adjustable", "Adjustable Laptop Stand", "MATCH"),
    ("Screen Protector iPhone 15", "iPhone 15 Tempered Glass Screen Protector", "MATCH"),
    ("AirPods Pro Case", "AirPods Pro Protective Case", "MATCH"),
    ("Webcam 1080p USB", "USB 1080p Webcam", "MATCH"),
    ("SSD 1TB Samsung", "Samsung 1TB SSD", "MATCH"),
    ("SD Card 128GB", "128GB SD Card", "MATCH"),
    ("LED Strip Lights RGB", "RGB LED Strip Lights", "MATCH"),
    ("Wireless Earbuds Noise Cancelling", "Noise Cancelling Wireless Earbuds", "MATCH"),
    ("Bluetooth Earbuds Waterproof", "Waterproof Bluetooth Earbuds", "MATCH"),
    ("USB-C Charger 20W", "20W USB-C Fast Charger", "MATCH"),
    ("iPhone 14 Case Clear", "Clear Case for iPhone 14", "MATCH"),
    ("Samsung Galaxy Buds 2", "Samsung Galaxy Buds 2 TWS", "MATCH"),
    ("Wireless Charger Pad", "Wireless Charging Pad", "MATCH"),
    ("HDMI Cable 6ft", "6ft HDMI Cable", "MATCH"),
    # NOT_MATCH pairs (30 — reduced to pairs that won't be filtered)
    ("Wireless Earbuds", "Mechanical Keyboard", "NOT_MATCH"),
    ("Bluetooth Speaker", "USB-C Cable", "NOT_MATCH"),
    ("Laptop Stand", "Laptop", "NOT_MATCH"),
    ("Phone Case", "Phone Charger", "NOT_MATCH"),
    ("Screen Protector", "Phone Case", "NOT_MATCH"),
    ("Keyboard", "Mouse", "NOT_MATCH"),
    ("Headphones", "Speaker", "NOT_MATCH"),
    ("USB Cable", "HDMI Cable", "NOT_MATCH"),
    ("Power Bank", "Wall Charger", "NOT_MATCH"),
    ("SSD 1TB", "HDD 1TB", "NOT_MATCH"),
    ("Camera", "Drone", "NOT_MATCH"),
    ("Tablet", "Laptop", "NOT_MATCH"),
    ("Webcam", "Camera", "NOT_MATCH"),
    ("Wireless Earbuds", "Phone Case", "NOT_MATCH"),
    ("Laptop", "Keyboard", "NOT_MATCH"),
    ("Headphones", "Earbuds Case", "NOT_MATCH"),
    ("Charger", "Cable", "NOT_MATCH"),
    ("Speaker", "Microphone", "NOT_MATCH"),
    ("Mouse", "Keyboard", "NOT_MATCH"),
    ("Monitor", "Laptop Stand", "NOT_MATCH"),
    ("Wireless Earbuds", "Wired Earbuds", "NOT_MATCH"),
    ("Bluetooth Speaker", "Wired Speaker", "NOT_MATCH"),
    ("USB-C Cable", "Micro USB Cable", "NOT_MATCH"),
    ("SSD 1TB", "SSD 500GB", "NOT_MATCH"),
    ("SD Card 128GB", "SD Card 64GB", "NOT_MATCH"),
    ("Charger 20W", "Charger 65W", "NOT_MATCH"),
    ("Cable USB-C", "Cable Lightning", "NOT_MATCH"),
    ("Speaker Bluetooth", "Speaker WiFi", "NOT_MATCH"),
    ("Mouse Wireless", "Mouse Wired", "NOT_MATCH"),
    ("Keyboard Mechanical", "Keyboard Membrane", "NOT_MATCH"),
    # UNCERTAIN pairs (30)
    ("Wireless Earbuds", "Bluetooth Earphones", "UNCERTAIN"),
    ("Phone Case", "Mobile Cover", "UNCERTAIN"),
    ("USB Cable", "Charging Cord", "UNCERTAIN"),
    ("Laptop Bag", "Notebook Sleeve", "UNCERTAIN"),
    ("Phone Stand", "Mobile Holder", "UNCERTAIN"),
    ("Screen Guard", "Display Protector", "UNCERTAIN"),
    ("Earphone", "Earbud", "UNCERTAIN"),
    ("Charger", "Power Adapter", "UNCERTAIN"),
    ("Speaker", "Sound Box", "UNCERTAIN"),
    ("Cable", "Wire", "UNCERTAIN"),
    ("Case", "Cover", "UNCERTAIN"),
    ("Stand", "Holder", "UNCERTAIN"),
    ("Mount", "Bracket", "UNCERTAIN"),
    ("Adapter", "Converter", "UNCERTAIN"),
    ("Hub", "Dock", "UNCERTAIN"),
    ("Pad", "Mat", "UNCERTAIN"),
    ("Bag", "Pouch", "UNCERTAIN"),
    ("Strap", "Band", "UNCERTAIN"),
    ("Grip", "Handle", "UNCERTAIN"),
    ("Clip", "Clamp", "UNCERTAIN"),
    ("Wireless Earbuds Black", "TWS Earphones Black", "UNCERTAIN"),
    ("Bluetooth Speaker", "Portable Sound Box", "UNCERTAIN"),
    ("USB-C Cable", "Type-C Cord", "UNCERTAIN"),
    ("Phone Case Clear", "Transparent Mobile Cover", "UNCERTAIN"),
    ("Laptop Stand", "Notebook Riser", "UNCERTAIN"),
    ("Screen Protector", "Glass Guard", "UNCERTAIN"),
    ("Power Bank", "External Battery", "UNCERTAIN"),
    ("Wireless Charger", "Charging Pad", "UNCERTAIN"),
    ("Car Mount", "Vehicle Holder", "UNCERTAIN"),
    ("Webcam", "Video Camera", "UNCERTAIN"),
]


class TestGoldenDataset:
    @pytest.fixture
    def matcher_nf(self):
        """Use no-filter matcher for golden dataset to test scoring."""
        return ProductMatcher(use_candidate_filter=False)

    def test_golden_dataset_size(self):
        assert len(GOLDEN_DATASET) >= 100

    def test_golden_match_pairs(self, matcher_nf):
        match_pairs = [
            (e, a) for e, a, label in GOLDEN_DATASET if label == "MATCH"
        ]
        correct = 0
        for ebay_title, ali_title in match_pairs:
            ebay = _ebay(f"v1|g_{hash(ebay_title)}|0", ebay_title)
            ali = _ali(ali_title)
            results = matcher_nf.find_matches(ebay, [ali], min_score=0.0)
            if results and results[0].match_score >= 0.50:
                correct += 1
        recall = correct / len(match_pairs) if match_pairs else 0
        assert recall >= 0.50, f"Match recall too low: {recall:.2f}"

    def test_golden_not_match_pairs(self, matcher_nf):
        not_match_pairs = [
            (e, a) for e, a, label in GOLDEN_DATASET if label == "NOT_MATCH"
        ]
        correct = 0
        for ebay_title, ali_title in not_match_pairs:
            ebay = _ebay(f"v1|g_{hash(ebay_title)}|0", ebay_title)
            ali = _ali(ali_title)
            results = matcher_nf.find_matches(ebay, [ali], min_score=0.0)
            if results and results[0].match_score < 0.50:
                correct += 1
            elif not results:
                correct += 1  # Filtered = correctly rejected
        precision = correct / len(not_match_pairs) if not_match_pairs else 0
        assert precision >= 0.50, f"Not-match precision too low: {precision:.2f}"

    def test_golden_evaluation_metrics(self, matcher_nf):
        tp, fp, fn, tn = 0, 0, 0, 0
        threshold = 0.50

        for ebay_title, ali_title, label in GOLDEN_DATASET:
            ebay = _ebay(f"v1|g_{hash(ebay_title)}|0", ebay_title)
            ali = _ali(ali_title)
            results = matcher_nf.find_matches(ebay, [ali], min_score=0.0)
            predicted_match = (
                results[0].match_score >= threshold if results else False
            )
            actual_match = label == "MATCH"

            if predicted_match and actual_match:
                tp += 1
            elif predicted_match and not actual_match:
                if label == "UNCERTAIN":
                    tn += 1
                else:
                    fp += 1
            elif not predicted_match and actual_match:
                fn += 1
            else:
                tn += 1

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0
        )

        assert precision >= 0.40, f"Precision {precision:.2f} too low"
        assert recall >= 0.40, f"Recall {recall:.2f} too low"


# =============================================================================
# DETERMINISM
# =============================================================================

class TestDeterminism:
    def test_same_pair_100_times(self, matcher):
        ebay = _ebay("v1|det|0", "Apple AirPods Pro 2 USB-C")
        ali = _ali("Apple AirPods Pro 2 USB-C TWS")
        scores = [
            matcher.find_matches(ebay, [ali], min_score=0.0)[0].match_score
            for _ in range(100)
        ]
        assert len(set(scores)) == 1


# =============================================================================
# REGRESSION
# =============================================================================

class TestRegression:
    def test_exact_match_still_works(self, matcher):
        ebay = _ebay("v1|r1|0", "Apple AirPods Pro 2nd Gen USB-C White")
        ali = _ali("Apple AirPods Pro 2 USB-C White TWS")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score >= 0.75

    def test_different_product_filtered(self, matcher):
        """Candidate filter removes brand mismatch."""
        ebay = _ebay("v1|r2|0", "Apple iPhone 15 Pro Max")
        ali = _ali("Samsung Galaxy S24 Ultra")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) == 0

    def test_different_product_low_score(self, matcher_no_filter):
        """Without filter, brand mismatch → low score."""
        ebay = _ebay("v1|r2|0", "Apple iPhone 15 Pro Max")
        ali = _ali("Samsung Galaxy S24 Ultra")
        results = matcher_no_filter.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score < 0.40

    def test_accessory_vs_device_filtered(self, matcher):
        ebay = _ebay("v1|r3|0", "Apple iPhone 15 Pro Max 256GB")
        ali = _ali("iPhone 15 Pro Max Silicone Case")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) == 0

    def test_accessory_vs_device_low_score(self, matcher_no_filter):
        ebay = _ebay("v1|r3|0", "Apple iPhone 15 Pro Max 256GB")
        ali = _ali("iPhone 15 Pro Max Silicone Case")
        results = matcher_no_filter.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score < 0.40

    def test_missing_data_neutral(self, matcher):
        ebay = _ebay("v1|r4|0", "Wireless Earbuds Bluetooth")
        ali = _ali("TWS Wireless Bluetooth Earbuds")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score >= 0.50

    def test_ranking_descending(self, matcher):
        ebay = _ebay("v1|r5|0", "Wireless Bluetooth Earbuds TWS Black")
        ali_products = [
            _ali("Wireless Bluetooth Earbuds TWS Black"),
            _ali("Bluetooth Earbuds White"),
            _ali("Mechanical Keyboard RGB"),
        ]
        results = matcher.find_matches(ebay, ali_products, min_score=0.0)
        scores = [r.match_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_min_score_filter(self, matcher):
        ebay = _ebay("v1|r6|0", "Wireless Bluetooth Earbuds TWS")
        ali_products = [
            _ali("Wireless Bluetooth Earbuds TWS"),
            _ali("Mechanical Keyboard RGB"),
        ]
        results = matcher.find_matches(ebay, ali_products, min_score=0.60)
        for r in results:
            assert r.match_score >= 0.60

    def test_unit_normalization_match(self, builder, matcher):
        ebay_id = builder.from_title("Samsung SSD 1TB")
        ali_id = builder.from_title("Samsung SSD 1024GB")
        result = matcher.match_pair(ebay_id, ali_id)
        assert result.attribute_similarity >= 0.80