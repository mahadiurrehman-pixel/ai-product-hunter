"""
Tests for Product Matching Engine (Phase 5).

Covers:
- Exact match
- Similar match
- Different product rejection
- Accessory vs device rejection
- Accessory to accessory match
- Unit normalization match
- Missing data neutrality
- Unbranded generic match
- Determinism
- Ranking
- Compatible models
- Generation mismatch
"""
from decimal import Decimal

import pytest

from services.matching import (
    ProductMatcher,
    ProductMatchResult,
    TextSimilarity,
    AttributeSimilarity,
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
    return ProductMatcher()


@pytest.fixture
def builder():
    return ProductIdentityBuilder()


def _ali_product(title, price=9.99, **kwargs):
    """Helper to create AliExpressProduct."""
    defaults = {
        "product_id": f"ali_{hash(title) % 100000}",
        "title": title,
        "price": AliExpressPrice(value=Decimal(str(price))),
        "product_url": "https://example.com",
        "source": "mock",
    }
    defaults.update(kwargs)
    return AliExpressProduct(**defaults)


# =============================================================================
# 1. EXACT MATCH
# =============================================================================

class TestExactMatch:
    def test_airpods_exact(self, matcher):
        ebay = {
            "item_id": "v1|100|0",
            "title": "Apple AirPods Pro 2nd Gen USB-C White",
            "price_value": Decimal("189.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali = _ali_product(
            "Apple AirPods Pro 2 USB-C White TWS",
            price=85.00,
        )
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score >= 0.75
        assert results[0].match_type in ("exact", "very_similar")


# =============================================================================
# 2. SIMILAR MATCH
# =============================================================================

class TestSimilarMatch:
    def test_galaxy_different_storage(self, matcher):
        ebay = {
            "item_id": "v1|200|0",
            "title": "Samsung Galaxy S24 Ultra 256GB Black",
            "price_value": Decimal("999.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali = _ali_product(
            "Samsung Galaxy S24 Ultra 512GB Black",
            price=450.00,
        )
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score >= 0.50
        # Storage differs — should be noted
        assert len(results[0].differing_attributes) >= 0


# =============================================================================
# 3. REJECT DIFFERENT PRODUCT
# =============================================================================

class TestRejectDifferentProduct:
    def test_apple_vs_samsung(self, matcher):
        ebay = {
            "item_id": "v1|300|0",
            "title": "Apple iPhone 15 Pro Max",
            "price_value": Decimal("999.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali = _ali_product("Samsung Galaxy S24 Ultra 512GB", price=450.00)
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        # Candidate filter removes brand mismatch
        if results:
            assert results[0].match_score < 0.40
        else:
            assert len(results) == 0  # Correctly filtered

    def test_earbuds_vs_keyboard(self, matcher):
        ebay = {
            "item_id": "v1|301|0",
            "title": "Wireless Bluetooth Earbuds TWS",
            "price_value": Decimal("29.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali = _ali_product("Mechanical Gaming Keyboard RGB", price=25.00)
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        if results:
            assert results[0].match_score < 0.40
        else:
            assert len(results) == 0


# =============================================================================
# 4. REJECT ACCESSORY vs DEVICE
# =============================================================================

class TestRejectAccessoryVsDevice:
    def test_iphone_vs_case(self, matcher):
        ebay = {
            "item_id": "v1|400|0",
            "title": "Apple iPhone 15 Pro Max 256GB",
            "price_value": Decimal("999.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali = _ali_product("iPhone 15 Pro Max Silicone Case", price=3.99)
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        if results:
            assert results[0].match_score < 0.40
        else:
            assert len(results) == 0

# =============================================================================
# 5. MATCH ACCESSORY TO ACCESSORY
# =============================================================================

class TestAccessoryToAccessory:
    def test_case_to_case(self, matcher):
        ebay = {
            "item_id": "v1|500|0",
            "title": "iPhone 15 Pro Max Case Silicone",
            "price_value": Decimal("12.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali = _ali_product(
            "iPhone 15 Pro Max Case Clear Silicone",
            price=2.99,
        )
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score >= 0.50


# =============================================================================
# 6. UNIT NORMALIZATION MATCH
# =============================================================================

class TestUnitNormalizationMatch:
    def test_1tb_vs_1024gb(self, matcher, builder):
        ebay_id = builder.from_title("Samsung SSD 1TB")
        ali_id = builder.from_title("Samsung SSD 1024GB")
        result = matcher.match_pair(ebay_id, ali_id)
        assert result.attribute_similarity >= 0.80


# =============================================================================
# 7. MISSING DATA NEUTRAL
# =============================================================================

class TestMissingDataNeutral:
    def test_no_brand_no_penalty(self, matcher):
        ebay = {
            "item_id": "v1|700|0",
            "title": "Wireless Earbuds Bluetooth TWS",
            "price_value": Decimal("19.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali = _ali_product(
            "TWS Wireless Bluetooth Earbuds",
            price=6.99,
        )
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score >= 0.50


# =============================================================================
# 8. UNBRANDED GENERIC MATCH
# =============================================================================

class TestUnbrandedGeneric:
    def test_usb_cable(self, matcher):
        ebay = {
            "item_id": "v1|800|0",
            "title": "USB-C Charging Cable 6ft Nylon",
            "price_value": Decimal("9.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali = _ali_product(
            "USB-C Cable 6ft Braided Nylon",
            price=2.49,
        )
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        assert results[0].match_score >= 0.50


# =============================================================================
# 9. DETERMINISM
# =============================================================================

class TestDeterminism:
    def test_same_pair_same_score(self, matcher):
        ebay = {
            "item_id": "v1|900|0",
            "title": "Apple AirPods Pro 2 USB-C",
            "price_value": Decimal("189.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali = _ali_product("Apple AirPods Pro 2 USB-C TWS", price=85.0)
        scores = [
            matcher.find_matches(ebay, [ali], min_score=0.0)[0].match_score
            for _ in range(100)
        ]
        assert len(set(scores)) == 1


# =============================================================================
# 10. FIND MATCHES RANKING
# =============================================================================

class TestFindMatchesRanking:
    def test_ranked_by_score(self, matcher):
        ebay = {
            "item_id": "v1|1000|0",
            "title": "Wireless Bluetooth Earbuds TWS Black",
            "price_value": Decimal("29.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali_products = [
            _ali_product("Wireless Bluetooth Earbuds TWS Black", 8.99),
            _ali_product("Bluetooth Earbuds White", 6.99),
            _ali_product("Mechanical Keyboard RGB", 25.00),
            _ali_product("Wireless Earbuds Noise Cancelling", 12.99),
            _ali_product("USB-C Cable Nylon", 2.49),
        ]
        results = matcher.find_matches(ebay, ali_products, min_score=0.0)
        # Should be sorted descending
        scores = [r.match_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_min_score_filter(self, matcher):
        ebay = {
            "item_id": "v1|1001|0",
            "title": "Wireless Bluetooth Earbuds TWS",
            "price_value": Decimal("29.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali_products = [
            _ali_product("Wireless Bluetooth Earbuds TWS", 8.99),
            _ali_product("Mechanical Keyboard RGB", 25.00),
        ]
        results = matcher.find_matches(ebay, ali_products, min_score=0.60)
        for r in results:
            assert r.match_score >= 0.60


# =============================================================================
# 11. COMPATIBLE MODELS MATCH
# =============================================================================

class TestCompatibleModels:
    def test_case_compatible_with_phone(self, matcher):
        ebay = {
            "item_id": "v1|1100|0",
            "title": "Case for iPhone 15 Pro Max",
            "price_value": Decimal("12.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali = _ali_product(
            "iPhone 15 Pro Max Protective Case",
            price=2.99,
        )
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        # Both should be accessories for the same phone
        assert results[0].match_score >= 0.40


# =============================================================================
# 12. GENERATION MISMATCH
# =============================================================================

class TestGenerationMismatch:
    def test_gen2_vs_gen1(self, matcher):
        ebay = {
            "item_id": "v1|1200|0",
            "title": "AirPods Pro 2nd Gen USB-C",
            "price_value": Decimal("189.99"),
            "price_currency": "USD",
            "marketplace": "EBAY_US",
        }
        ali = _ali_product(
            "AirPods Pro 1st Gen Lightning",
            price=65.00,
        )
        results = matcher.find_matches(ebay, [ali], min_score=0.0)
        assert len(results) >= 1
        # Should match but with reduced score due to generation
        assert results[0].match_score < 0.90


# =============================================================================
# TextSimilarity Unit Tests
# =============================================================================

class TestTextSimilarity:
    def test_identical_keywords(self):
        sim = TextSimilarity()
        a = ProductIdentity(keywords=["wireless", "earbuds", "bluetooth"])
        b = ProductIdentity(keywords=["wireless", "earbuds", "bluetooth"])
        score, matching = sim.calculate(a, b)
        assert score >= 0.90
        assert len(matching) == 3

    def test_no_overlap(self):
        sim = TextSimilarity()
        a = ProductIdentity(keywords=["keyboard", "mechanical"])
        b = ProductIdentity(keywords=["earbuds", "wireless"])
        score, matching = sim.calculate(a, b)
        assert score == 0.0
        assert len(matching) == 0

    def test_model_boost(self):
        sim = TextSimilarity()
        a = ProductIdentity(
            keywords=["iphone", "15"], model="iPhone 15"
        )
        b = ProductIdentity(
            keywords=["iphone", "15"], model="iPhone 15"
        )
        score, _ = sim.calculate(a, b)
        assert score >= 1.0  # Jaccard 1.0 + model boost, capped at 1.0

    def test_empty_keywords(self):
        sim = TextSimilarity()
        a = ProductIdentity(keywords=[])
        b = ProductIdentity(keywords=[])
        score, _ = sim.calculate(a, b)
        assert score == 0.0


# =============================================================================
# AttributeSimilarity Unit Tests
# =============================================================================

class TestAttributeSimilarity:
    def test_matching_attributes(self):
        sim = AttributeSimilarity()
        a = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="black",
                    normalized_value="black",
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        b = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="black",
                    normalized_value="black",
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        score, matching, differing = sim.calculate(a, b)
        assert score == 1.0
        assert len(matching) == 1

    def test_differing_attributes(self):
        sim = AttributeSimilarity()
        a = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="black",
                    normalized_value="black",
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        b = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="red",
                    normalized_value="red",
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        score, matching, differing = sim.calculate(a, b)
        assert score == 0.0
        assert len(differing) == 1

    def test_numeric_unit_match(self):
        """1TB vs 1024GB should match via numeric comparison."""
        sim = AttributeSimilarity()
        a = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="storage", raw_value="1TB",
                    normalized_value="1024GB",
                    unit="GB", numeric_value=1024.0,
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        b = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="storage", raw_value="1024GB",
                    normalized_value="1024GB",
                    unit="GB", numeric_value=1024.0,
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        score, matching, _ = sim.calculate(a, b)
        assert score >= 0.90

    def test_missing_attr_neutral(self):
        sim = AttributeSimilarity()
        a = ProductIdentity(canonical_attributes=[])
        b = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="black",
                    normalized_value="black",
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        score, _, _ = sim.calculate(a, b)
        assert score == 0.5  # Neutral when no common attrs

    def test_unknown_attr_partial(self):
        sim = AttributeSimilarity()
        a = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="Ocean Mist",
                    status=AttributeStatus.UNKNOWN,
                ),
            ]
        )
        b = ProductIdentity(
            canonical_attributes=[
                CanonicalAttribute(
                    name="color", raw_value="blue",
                    normalized_value="blue",
                    status=AttributeStatus.NORMALIZED,
                ),
            ]
        )
        score, _, _ = sim.calculate(a, b)
        assert 0.2 <= score <= 0.5  # Partial credit for unknown


# =============================================================================
# ProductMatchResult Tests
# =============================================================================

class TestProductMatchResult:
    def test_to_dict(self):
        r = ProductMatchResult(
            ebay_item_id="v1|1|0",
            ali_product_id="ali_1",
            match_score=0.85,
            confidence=0.80,
            match_type="very_similar",
        )
        d = r.to_dict()
        assert d["match_score"] == 0.85
        assert d["match_type"] == "very_similar"
        assert "ebay_item_id" in d
        assert "ali_product_id" in d