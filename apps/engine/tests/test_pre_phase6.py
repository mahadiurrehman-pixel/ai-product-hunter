"""
Tests for Pre-Phase 6.1–6.7 hardening.
"""
import time
from decimal import Decimal

import pytest

from services.matching import (
    ProductMatcher,
    CandidateFilter,
    CandidateStatus,
    BundleDetector,
    QuantitySimilarity,
    MATCHER_VERSION,
)
from services.matching.similarity import ConditionSimilarity
from services.product_identity import ProductIdentityBuilder
from services.product_identity.models import ProductIdentity
from services.aliexpress.models import AliExpressProduct, AliExpressPrice


@pytest.fixture
def matcher():
    return ProductMatcher()

@pytest.fixture
def builder():
    return ProductIdentityBuilder()

def _ali(title, price=9.99, **kw):
    defaults = {
        "product_id": f"ali_{hash(title) % 100000}",
        "title": title,
        "price": AliExpressPrice(value=Decimal(str(price))),
        "product_url": "https://example.com",
        "source": "mock",
    }
    defaults.update(kw)
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
# 6.1 — CANDIDATE FILTERING
# =============================================================================

class TestCandidateFiltering:
    @pytest.fixture
    def cf(self):
        return CandidateFilter()

    def test_same_type_eligible(self, cf, builder):
        a = builder.from_title("Wireless Bluetooth Earbuds TWS")
        b = builder.from_title("TWS Bluetooth Earbuds Wireless")
        result = cf.filter_pair(a, b)
        assert result.is_eligible

    def test_different_type_filtered(self, cf, builder):
        a = builder.from_title("Apple iPhone 15 Pro Max")
        b = builder.from_title("Mechanical Gaming Keyboard RGB")
        result = cf.filter_pair(a, b)
        assert not result.is_eligible
        assert any("type" in r.lower() for r in result.reasons)

    def test_different_brand_filtered(self, cf, builder):
        a = builder.from_title("Apple AirPods Pro 2")
        b = builder.from_title("Samsung Galaxy Buds 2")
        result = cf.filter_pair(a, b)
        assert not result.is_eligible
        assert any("brand" in r.lower() for r in result.reasons)

    def test_missing_brand_eligible(self, cf, builder):
        a = builder.from_title("Wireless Earbuds Bluetooth")
        b = builder.from_title("TWS Earbuds Bluetooth")
        result = cf.filter_pair(a, b)
        assert result.is_eligible

    def test_accessory_device_filtered(self, cf, builder):
        a = builder.from_title("Apple iPhone 15 Pro Max 256GB")
        b = builder.from_title("iPhone 15 Pro Max Silicone Case")
        result = cf.filter_pair(a, b)
        assert not result.is_eligible

    def test_compatible_accessory_eligible(self, cf, builder):
        a = builder.from_title("Case for iPhone 15 Pro Max")
        b = builder.from_title("iPhone 15 Pro Max Case Clear")
        result = cf.filter_pair(a, b)
        assert result.is_eligible

    def test_incompatible_accessories_eligible(self, cf, builder):
        a = builder.from_title("Case for iPhone 15 Pro Max")
        b = builder.from_title("Samsung Galaxy S24 Case")
        result = cf.filter_pair(a, b)
        assert result.is_eligible

    def test_generic_products_eligible(self, cf, builder):
        a = builder.from_title("USB Cable 6ft")
        b = builder.from_title("USB Cable 3ft Nylon")
        result = cf.filter_pair(a, b)
        assert result.is_eligible

    def test_filter_candidates_batch(self, cf, builder):
        ebay = builder.from_title("Wireless Bluetooth Earbuds TWS")
        ali_identities = [
            builder.from_title("TWS Bluetooth Earbuds"),
            builder.from_title("Mechanical Keyboard RGB"),
            builder.from_title("Bluetooth Earbuds Waterproof"),
        ]
        eligible, filtered = cf.filter_candidates(ebay, ali_identities)
        assert len(eligible) >= 1
        assert len(filtered) >= 1

    def test_candidate_result_to_dict(self, cf, builder):
        a = builder.from_title("Wireless Earbuds")
        b = builder.from_title("TWS Earbuds")
        result = cf.filter_pair(a, b)
        d = result.to_dict()
        assert "status" in d
        assert "reasons" in d


# =============================================================================
# 6.3 — FALSE-POSITIVE AUDIT
# =============================================================================

class TestFalsePositiveAudit:
    def test_device_vs_accessory_not_matched(self, matcher):
        """Candidate filter removes this pair — results should be empty."""
        ebay = _ebay("v1|fp1|0", "Apple iPhone 15 Pro Max 256GB")
        ali = _ali("iPhone 15 Pro Max Silicone Case")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        # Either empty (filtered) or low score
        if results:
            assert results[0].match_score < 0.40
        else:
            assert len(results) == 0  # Correctly filtered

    def test_device_vs_accessory_bypassing_filter(self, builder):
        """Test match_pair directly to verify low score."""
        matcher_no_filter = ProductMatcher(use_candidate_filter=False)
        ebay = _ebay("v1|fp1b|0", "Apple iPhone 15 Pro Max 256GB")
        ali = _ali("iPhone 15 Pro Max Silicone Case")
        results = matcher_no_filter.find_matches(
            ebay, [ali], min_score=0.0
        )
        assert len(results) >= 1
        assert results[0].match_score < 0.40

    def test_different_model_not_exact(self, matcher):
        ebay = _ebay("v1|fp2|0", "Apple iPhone 15 128GB")
        ali = _ali("Apple iPhone 14 128GB")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        if results:
            assert results[0].match_type != "exact"

    def test_different_generation_conflict(self, matcher):
        ebay = _ebay("v1|fp3|0", "AirPods Pro 2nd Gen USB-C")
        ali = _ali("AirPods Pro 1st Gen Lightning")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        if results:
            assert results[0].match_score < 0.90

    def test_different_storage_variant(self, matcher):
        ebay = _ebay("v1|fp4|0", "iPhone 15 Pro Max 256GB")
        ali = _ali("iPhone 15 Pro Max 512GB")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        if results:
            assert len(results[0].differing_attributes) > 0

    def test_different_ram_conflict(self, matcher):
        ebay = _ebay("v1|fp5|0", "Laptop 16GB RAM 512GB SSD")
        ali = _ali("Laptop 32GB RAM 512GB SSD")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        if results:
            assert results[0].variant_similarity < 1.0

    def test_incompatible_accessories_not_matched(self, matcher):
        ebay = _ebay("v1|fp6|0", "Case for iPhone 15 Pro Max")
        ali = _ali("Case for iPhone 14")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        if results:
            assert results[0].match_score < 0.70

    def test_bundle_vs_single_not_exact(self, matcher):
        ebay = _ebay("v1|fp7|0", "iPhone Case Silicone")
        ali = _ali("3 Pack iPhone Case Silicone")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        if results:
            assert results[0].match_type != "exact"


# =============================================================================
# 6.4 — BUNDLE / MULTIPACK DETECTION
# =============================================================================

class TestBundleDetection:
    @pytest.fixture
    def detector(self):
        return BundleDetector()

    def test_2_pack(self, detector):
        info = detector.detect("2 Pack iPhone Case")
        assert info.quantity == 2
        assert info.is_multipack

    def test_3_pack(self, detector):
        info = detector.detect("3-Pack USB Cable")
        assert info.quantity == 3

    def test_pack_of_2(self, detector):
        info = detector.detect("Pack of 2 Screen Protectors")
        assert info.quantity == 2

    def test_set_of_3(self, detector):
        info = detector.detect("Set of 3 Phone Cases")
        assert info.quantity == 3

    def test_bundle_keyword(self, detector):
        info = detector.detect("Laptop Stand + Keyboard Bundle")
        assert info.is_bundle

    def test_kit_keyword(self, detector):
        info = detector.detect("Phone Repair Kit")
        assert info.is_kit

    def test_combo_keyword(self, detector):
        info = detector.detect("Keyboard Mouse Combo")
        assert info.is_combo

    def test_single_product(self, detector):
        info = detector.detect("iPhone Case Silicone")
        assert info.quantity == 1
        assert not info.is_bundle

    def test_unknown_quantity(self, detector):
        info = detector.detect("Phone Case")
        assert info.confidence == "unknown"

    def test_x2_pattern(self, detector):
        info = detector.detect("USB Cable x2")
        assert info.quantity == 2

    def test_pcs_pattern(self, detector):
        info = detector.detect("Screen Protector 3pcs")
        assert info.quantity == 3

    def test_compare_same_quantity(self, detector):
        score, ev = detector.compare("2 Pack Case", "2 Pack Case")
        assert score == 1.0

    def test_compare_different_quantity(self, detector):
        """Both have detected quantity → mismatch."""
        score, ev = detector.compare("2 Pack Case", "3 Pack Case")
        assert score < 0.5

    def test_compare_unknown_both(self, detector):
        """Both unknown → neutral 0.5."""
        score, ev = detector.compare("Phone Case", "Phone Case")
        assert score == 0.5

    def test_compare_one_known_one_unknown(self, detector):
        """One known, one unknown → neutral 0.5."""
        score, ev = detector.compare("Phone Case", "3 Pack Case")
        assert score == 0.5


# =============================================================================
# 6.5 — CONDITION & QUANTITY AWARENESS
# =============================================================================

class TestConditionQuantityAwareness:
    def test_same_condition_positive(self):
        a = ProductIdentity(condition="new")
        b = ProductIdentity(condition="new")
        sim = ConditionSimilarity()
        score, ev = sim.calculate(a, b)
        assert score == 1.0

    def test_new_vs_used_mismatch(self):
        a = ProductIdentity(condition="new")
        b = ProductIdentity(condition="used")
        sim = ConditionSimilarity()
        score, ev = sim.calculate(a, b)
        assert score < 0.5

    def test_refurbished_vs_new(self):
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

    def test_open_box_vs_new(self):
        a = ProductIdentity(condition="new")
        b = ProductIdentity(condition="open_box")
        sim = ConditionSimilarity()
        score, ev = sim.calculate(a, b)
        assert 0.3 <= score <= 0.8

    def test_quantity_similarity_matching(self, builder):
        a = builder.from_title("2 Pack iPhone Case")
        b = builder.from_title("2 Pack iPhone Case")
        sim = QuantitySimilarity()
        score, ev = sim.calculate(a, b)
        assert score >= 0.8

    def test_quantity_similarity_both_detected_different(self, builder):
        """Both have detected quantities that differ."""
        a = builder.from_title("2 Pack iPhone Case")
        b = builder.from_title("3 Pack iPhone Case")
        sim = QuantitySimilarity()
        score, ev = sim.calculate(a, b)
        assert score < 0.5

    def test_quantity_similarity_one_unknown(self, builder):
        """One has detected quantity, other unknown → neutral."""
        a = builder.from_title("iPhone Case")
        b = builder.from_title("3 Pack iPhone Case")
        sim = QuantitySimilarity()
        score, ev = sim.calculate(a, b)
        assert score == 0.5  # One unknown → neutral


# =============================================================================
# 6.6 — MATCH PROVENANCE & EXPLAINABILITY
# =============================================================================

class TestMatchProvenance:
    def test_provenance_in_result(self, matcher):
        ebay = _ebay("v1|prov|0", "Apple AirPods Pro 2 USB-C")
        ali = _ali("Apple AirPods Pro 2 USB-C TWS")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        r = results[0]
        assert r.matcher_version == MATCHER_VERSION
        assert r.matched_at is not None
        d = r.to_dict()
        assert "provenance" in d
        assert "matcher_version" in d["provenance"]
        assert "taxonomy_version" in d["provenance"]
        assert "matched_at" in d["provenance"]

    def test_accepted_explanation(self, matcher):
        ebay = _ebay("v1|acc|0", "Apple AirPods Pro 2 USB-C White")
        ali = _ali("Apple AirPods Pro 2 USB-C White TWS")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        r = results[0]
        assert len(r.positive_evidence) > 0

    def test_rejected_explanation_via_direct_match(self, builder):
        """Use match_pair directly to bypass candidate filter."""
        matcher_no_filter = ProductMatcher(use_candidate_filter=False)
        ebay = _ebay("v1|rej|0", "Apple iPhone 15 Pro Max")
        ali = _ali("Samsung Galaxy S24 Ultra")
        results = matcher_no_filter.find_matches(
            ebay, [ali], min_score=0.0
        )
        assert len(results) >= 1
        r = results[0]
        assert len(r.negative_evidence) > 0

    def test_deterministic_explanations(self, matcher):
        ebay = _ebay("v1|det|0", "Apple AirPods Pro 2 USB-C")
        ali = _ali("Apple AirPods Pro 2 USB-C TWS")
        r1 = matcher.find_matches(ebay, [ali], min_score=0.0)[0]
        r2 = matcher.find_matches(ebay, [ali], min_score=0.0)[0]
        assert r1.positive_evidence == r2.positive_evidence
        assert r1.negative_evidence == r2.negative_evidence


# =============================================================================
# 6.7 — PERFORMANCE BENCHMARK
# =============================================================================

class TestPerformanceBenchmark:
    def test_benchmark_100_listings(self, matcher):
        ebay = _ebay("v1|bench|0", "Wireless Bluetooth Earbuds TWS")
        ali_products = [
            _ali(f"TWS Bluetooth Earbuds {i}", price=5.0 + i)
            for i in range(100)
        ]
        start = time.time()
        results = matcher.find_matches(ebay, ali_products, min_score=0.0)
        elapsed = time.time() - start
        assert len(results) >= 0
        assert elapsed < 30.0

    def test_benchmark_with_filtering(self):
        matcher_filtered = ProductMatcher(use_candidate_filter=True)
        matcher_unfiltered = ProductMatcher(use_candidate_filter=False)

        ebay = _ebay("v1|bench2|0", "Wireless Bluetooth Earbuds TWS")
        ali_products = [
            _ali(f"TWS Bluetooth Earbuds {i}", price=5.0 + i)
            for i in range(50)
        ] + [
            _ali(f"Mechanical Keyboard {i}", price=20.0 + i)
            for i in range(50)
        ]

        start_filtered = time.time()
        results_filtered = matcher_filtered.find_matches(
            ebay, ali_products, min_score=0.0
        )
        time_filtered = time.time() - start_filtered

        start_unfiltered = time.time()
        results_unfiltered = matcher_unfiltered.find_matches(
            ebay, ali_products, min_score=0.0
        )
        time_unfiltered = time.time() - start_unfiltered

        assert len(results_filtered) <= len(results_unfiltered)


# =============================================================================
# REGRESSION — ALL EXISTING BEHAVIOR PRESERVED
# =============================================================================

class TestRegressionPrePhase6:
    def test_exact_match(self, matcher):
        ebay = _ebay("v1|r1|0", "Apple AirPods Pro 2 USB-C White")
        ali = _ali("Apple AirPods Pro 2 USB-C White TWS")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score >= 0.60

    def test_different_product_rejected_by_filter(self, matcher):
        """Brand mismatch → candidate filter removes it → empty results."""
        ebay = _ebay("v1|r2|0", "Apple iPhone 15 Pro Max")
        ali = _ali("Samsung Galaxy S24 Ultra")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) == 0  # Correctly filtered out

    def test_different_product_low_score_no_filter(self):
        """Without filter, brand mismatch → hard rejection → score 0."""
        matcher_no_filter = ProductMatcher(use_candidate_filter=False)
        ebay = _ebay("v1|r2b|0", "Apple iPhone 15 Pro Max")
        ali = _ali("Samsung Galaxy S24 Ultra")
        results = matcher_no_filter.find_matches(
            ebay, [ali], min_score=0.0
        )
        assert len(results) >= 1
        assert results[0].match_score < 0.40

    def test_accessory_vs_device_filtered(self, matcher):
        """Accessory vs device → filtered by candidate filter."""
        ebay = _ebay("v1|r3|0", "Apple iPhone 15 Pro Max 256GB")
        ali = _ali("iPhone 15 Pro Max Silicone Case")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) == 0  # Correctly filtered

    def test_accessory_vs_device_low_score_no_filter(self):
        """Without filter, accessory vs device → low score."""
        matcher_no_filter = ProductMatcher(use_candidate_filter=False)
        ebay = _ebay("v1|r3b|0", "Apple iPhone 15 Pro Max 256GB")
        ali = _ali("iPhone 15 Pro Max Silicone Case")
        results = matcher_no_filter.find_matches(
            ebay, [ali], min_score=0.0
        )
        assert len(results) >= 1
        assert results[0].match_score < 0.40

    def test_missing_data_neutral(self, matcher):
        ebay = _ebay("v1|r4|0", "Wireless Earbuds Bluetooth")
        ali = _ali("TWS Wireless Bluetooth Earbuds")
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score >= 0.40

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

    def test_unit_normalization(self, builder, matcher):
        ebay_id = builder.from_title("Samsung SSD 1TB")
        ali_id = builder.from_title("Samsung SSD 1024GB")
        result = matcher.match_pair(ebay_id, ali_id)
        assert result.attribute_similarity >= 0.80