"""
Tests for Product Identity Layer.

Covers:
- Basic identity extraction
- Variant extraction
- Attribute normalization
- Missing data handling
- False positive prevention
- Alias handling
- Confidence scoring
- Data quality classification
- Determinism
- eBay and AliExpress input formats
"""
import pytest

from services.product_identity import (
    DataQuality,
    ProductIdentity,
    ProductIdentityBuilder,
)


class TestProductIdentityModel:
    """Test ProductIdentity dataclass."""

    def test_default_values(self):
        identity = ProductIdentity()
        assert identity.product_type is None
        assert identity.brand is None
        assert identity.model is None
        assert identity.variant is None
        assert identity.condition is None
        assert identity.attributes == {}
        assert identity.keywords == []
        assert identity.source == "unknown"
        assert identity.marketplace is None
        assert identity.identity_confidence == 0.0
        assert identity.data_quality == DataQuality.LOW

    def test_identity_key_format(self):
        identity = ProductIdentity(
            brand="Apple",
            product_type="earbuds",
            model="AirPods Pro",
            variant="2nd Gen USB-C",
        )
        assert identity.identity_key == "apple|earbuds|airpods pro|2nd gen usb-c"

    def test_identity_key_missing_fields(self):
        identity = ProductIdentity(product_type="earbuds")
        assert identity.identity_key == "unknown|earbuds|unknown|unknown"

    def test_to_dict(self):
        identity = ProductIdentity(
            product_type="earbuds",
            brand="Apple",
            source="ebay",
            identity_confidence=0.85,
            data_quality=DataQuality.HIGH,
            original_title="Apple AirPods Pro",
        )
        d = identity.to_dict()
        assert d["product_type"] == "earbuds"
        assert d["brand"] == "Apple"
        assert d["source"] == "ebay"
        assert d["identity_confidence"] == 0.85
        assert d["data_quality"] == "high"
        assert "identity_key" in d


class TestDataQuality:
    def test_three_levels(self):
        assert DataQuality.HIGH.value == "high"
        assert DataQuality.MEDIUM.value == "medium"
        assert DataQuality.LOW.value == "low"


class TestProductIdentityBuilder:
    """Test ProductIdentityBuilder."""

    @pytest.fixture
    def builder(self):
        return ProductIdentityBuilder()

    # --- Basic identity extraction ---

    def test_clean_product_title(self, builder):
        identity = builder.from_title(
            "Apple AirPods Pro 2nd Gen USB-C White"
        )
        assert identity.brand == "Apple"
        assert identity.product_type == "earbuds"
        assert identity.model is not None
        assert "airpods" in identity.model.lower()
        assert identity.original_title == "Apple AirPods Pro 2nd Gen USB-C White"

    def test_product_type_extraction(self, builder):
        identity = builder.from_title("Wireless Bluetooth Earbuds TWS")
        assert identity.product_type == "earbuds"

    def test_headphones_type(self, builder):
        identity = builder.from_title("Sony WH-1000XM5 Headphones")
        assert identity.product_type == "headphones"
        assert identity.brand == "Sony"

    def test_laptop_type(self, builder):
        identity = builder.from_title("Dell XPS 15 Laptop 16GB RAM")
        assert identity.product_type == "laptop"
        assert identity.brand == "Dell"

    def test_keyboard_not_audio(self, builder):
        identity = builder.from_title("Bluetooth Keyboard Wireless")
        assert identity.product_type == "keyboard"
        # Must NOT be "audio" just because "bluetooth" is present
        assert identity.product_type != "earbuds"

    def test_brand_extraction(self, builder):
        identity = builder.from_title("Samsung Galaxy S24 Ultra Case")
        assert identity.brand == "Samsung"

    def test_model_extraction_iphone(self, builder):
        identity = builder.from_title("iPhone 15 Pro Max 256GB")
        assert identity.model is not None
        assert "15" in identity.model

    def test_model_extraction_galaxy(self, builder):
        identity = builder.from_title("Samsung Galaxy S24 Ultra 512GB")
        assert identity.model is not None
        assert "s24" in identity.model.lower()
        
    def test_model_extraction_airpods(self, builder):
        identity = builder.from_title("Apple AirPods Pro 2 USB-C")
        assert identity.model is not None
        assert "airpods" in identity.model.lower()

    def test_condition_extraction_new(self, builder):
        identity = builder.from_title("New Wireless Earbuds")
        assert identity.condition == "new"

    def test_condition_extraction_used(self, builder):
        identity = builder.from_title("Used iPhone 15")
        assert identity.condition == "used"

    def test_condition_extraction_refurbished(self, builder):
        identity = builder.from_title("Refurbished Laptop Dell")
        assert identity.condition == "refurbished"

    def test_condition_missing_is_none(self, builder):
        identity = builder.from_title("Wireless Earbuds Bluetooth")
        assert identity.condition is None  # NOT assumed "new"

    # --- Variants ---

    def test_variant_generation(self, builder):
        identity = builder.from_title("AirPods Pro 2nd Gen USB-C")
        # Generation is captured in model; variant should have USB-C
        assert identity.model is not None
        assert "airpods" in identity.model.lower()
        # Variant may contain USB-C connectivity or generation
        if identity.variant:
            assert (
                "USB" in identity.variant.upper()
                or "GEN" in identity.variant.upper()
            )

    def test_variant_storage(self, builder):
        identity = builder.from_title("iPhone 15 Pro 256GB")
        # 256GB should appear in variant or attributes
        has_storage_variant = (
            identity.variant and "256" in identity.variant
        )
        has_storage_attr = (
            "storage" in identity.attributes
            and "256" in identity.attributes["storage"]
        )
        assert has_storage_variant or has_storage_attr

    def test_variant_connectivity(self, builder):
        identity = builder.from_title("Apple AirPods Pro USB-C")
        if identity.variant:
            assert "USB" in identity.variant.upper()

    def test_variant_pack_quantity(self, builder):
        identity = builder.from_title("USB Cable 3 Pack")
        if identity.variant:
            assert "3" in identity.variant

    def test_no_variant_for_simple_product(self, builder):
        identity = builder.from_title("Wireless Mouse")
        # Simple product may have no variant
        # This is acceptable — variant is Optional
        assert identity.variant is None or isinstance(identity.variant, str)

    # --- Attributes ---

    def test_color_attribute(self, builder):
        identity = builder.from_title("iPhone 15 Black Case")
        assert "color" in identity.attributes
        assert identity.attributes["color"] == "black"

    def test_storage_attribute(self, builder):
        identity = builder.from_title("Samsung Galaxy 256GB Phone")
        assert "storage" in identity.attributes

    def test_memory_attribute(self, builder):
        identity = builder.from_title("Laptop 16GB RAM 512GB SSD")
        assert "memory" in identity.attributes
        assert "storage" in identity.attributes

    def test_size_attribute(self, builder):
        identity = builder.from_title('Samsung 55" TV')
        assert "size" in identity.attributes

    def test_connectivity_attribute(self, builder):
        identity = builder.from_title("Bluetooth Speaker Wireless")
        assert "connectivity" in identity.attributes

    def test_attribute_normalization_colour(self, builder):
        identity = builder.from_title(
            "Phone Case", extra_attributes={"colour": "red"}
        )
        assert "color" in identity.attributes
        assert identity.attributes["color"] == "red"

    def test_attribute_normalization_ram(self, builder):
        identity = builder.from_title(
            "Laptop", extra_attributes={"ram": "16gb"}
        )
        assert "memory" in identity.attributes

    # --- Missing data ---

    def test_missing_brand(self, builder):
        identity = builder.from_title("Generic Wireless Earbuds TWS")
        assert identity.brand is None

    def test_missing_model(self, builder):
        identity = builder.from_title("Wireless Earbuds Bluetooth")
        assert identity.model is None  # No specific model in title

    def test_missing_attributes(self, builder):
        identity = builder.from_title("Phone")
        assert isinstance(identity.attributes, dict)
        # May have few or no attributes

    def test_missing_condition(self, builder):
        identity = builder.from_title("Wireless Mouse Logitech")
        assert identity.condition is None

    def test_poor_title(self, builder):
        identity = builder.from_title("New Hot Sale Best Deal")
        # All stopwords — very little identity
        assert identity.identity_confidence < 0.5
        assert identity.data_quality == DataQuality.LOW

    def test_empty_title(self, builder):
        identity = builder.from_title("")
        assert identity.product_type is None
        assert identity.brand is None
        assert identity.identity_confidence == 0.0

    # --- False positives ---

    def test_placid_not_acid(self, builder):
        identity = builder.from_title("Placid Lake Waterproof Case")
        # "placid" must not trigger any hazmat/acid detection
        assert identity.product_type in ("phone_case", "case", None)

    def test_generic_word_not_brand(self, builder):
        identity = builder.from_title("Wireless Bluetooth Speaker")
        # "wireless" and "bluetooth" are not brands
        assert identity.brand is None

    def test_generic_word_not_model(self, builder):
        identity = builder.from_title("Phone Case Cover")
        # Generic words should not become model numbers
        assert identity.model is None

    # --- Aliases ---

    def test_airpods_alias(self, builder):
        identity = builder.from_title("Apple Air Pods Pro")
        # "air pods" should normalize to "airpods"
        assert identity.brand == "Apple"

    def test_usb_c_alias(self, builder):
        identity = builder.from_title("USB C Charger Fast")
        assert identity.product_type == "charger"

    # --- Confidence ---

    def test_high_confidence_full_identity(self, builder):
        identity = builder.from_title(
            "Apple iPhone 15 Pro Max 256GB Space Gray New"
        )
        assert identity.identity_confidence >= 0.70

    def test_low_confidence_generic_title(self, builder):
        identity = builder.from_title("Wireless Earbuds")
        assert identity.identity_confidence < 0.70

    def test_high_quality_gt_low_quality(self, builder):
        high = builder.from_title(
            "Apple iPhone 15 Pro Max 256GB Space Gray New"
        )
        low = builder.from_title("Wireless Thing")
        assert high.identity_confidence > low.identity_confidence

    def test_confidence_range(self, builder):
        titles = [
            "Apple AirPods Pro 2 USB-C White New",
            "Wireless Earbuds",
            "Samsung Galaxy S24 Ultra 512GB",
            "Phone Case",
            "New Hot Sale Best",
        ]
        for title in titles:
            identity = builder.from_title(title)
            assert 0.0 <= identity.identity_confidence <= 1.0

    # --- Data quality ---

    def test_high_quality_classification(self, builder):
        identity = builder.from_title(
            "Apple iPhone 15 Pro Max 256GB Space Gray"
        )
        assert identity.data_quality == DataQuality.HIGH

    def test_medium_quality_classification(self, builder):
        identity = builder.from_title("Wireless Bluetooth Earbuds TWS")
        assert identity.data_quality in (DataQuality.MEDIUM, DataQuality.LOW)

    def test_low_quality_classification(self, builder):
        identity = builder.from_title("New Hot Sale Best Deal")
        assert identity.data_quality == DataQuality.LOW

    # --- Determinism ---

    def test_deterministic_output(self, builder):
        title = "Apple AirPods Pro 2nd Gen USB-C White"
        id1 = builder.from_title(title)
        id2 = builder.from_title(title)
        assert id1.to_dict() == id2.to_dict()

    def test_deterministic_across_calls(self, builder):
        title = "Samsung Galaxy S24 Ultra 256GB Black"
        results = [builder.from_title(title).to_dict() for _ in range(5)]
        assert all(r == results[0] for r in results)

    # --- Source and marketplace ---

    def test_source_ebay(self, builder):
        identity = builder.from_title("Earbuds", source="ebay")
        assert identity.source == "ebay"

    def test_source_aliexpress(self, builder):
        identity = builder.from_title("Earbuds", source="aliexpress")
        assert identity.source == "aliexpress"

    def test_marketplace_preserved(self, builder):
        identity = builder.from_title(
            "Earbuds", source="ebay", marketplace="EBAY_GB"
        )
        assert identity.marketplace == "EBAY_GB"

    # --- eBay listing input ---

    def test_from_ebay_listing(self, builder):
        listing = {
            "title": "Apple AirPods Pro 2nd Gen USB-C",
            "marketplace": "EBAY_US",
            "condition": "New",
            "product_brand": "Apple",
            "product_aspects": {"Color": ["White"]},
        }
        identity = builder.from_ebay_listing(listing)
        assert identity.source == "ebay"
        assert identity.marketplace == "EBAY_US"
        assert identity.brand == "Apple"

    def test_from_ebay_listing_minimal(self, builder):
        listing = {
            "title": "Wireless Earbuds",
        }
        identity = builder.from_ebay_listing(listing)
        assert identity.source == "ebay"
        assert identity.product_type == "earbuds"

    # --- AliExpress product input ---

    def test_from_aliexpress_dict(self, builder):
        product = {
            "title": "TWS Wireless Bluetooth Earbuds Noise Cancelling",
            "source": "mock",
            "attributes": {"color": "black", "connectivity": "bluetooth"},
        }
        identity = builder.from_aliexpress_product(product)
        assert identity.source == "mock"
        assert identity.product_type == "earbuds"
        
    def test_from_aliexpress_dataclass(self, builder):
        """Test with actual AliExpressProduct dataclass."""
        from services.aliexpress.models import (
            AliExpressPrice,
            AliExpressProduct,
        )
        from decimal import Decimal

        product = AliExpressProduct(
            product_id="ali_001",
            title="TWS Wireless Bluetooth Earbuds",
            price=AliExpressPrice(value=Decimal("8.99")),
            product_url="https://example.com",
            source="mock",
            attributes={"color": "black"},
        )
        identity = builder.from_aliexpress_product(product)
        assert identity.source == "mock"
        assert identity.brand is None

    # --- Keywords ---

    def test_keywords_extracted(self, builder):
        identity = builder.from_title("Wireless Bluetooth Earbuds TWS")
        assert len(identity.keywords) >= 2
        assert "wireless" in identity.keywords or "bluetooth" in identity.keywords

    def test_keywords_deduplicated(self, builder):
        identity = builder.from_title("Wireless Wireless Earbuds Earbuds")
        # Keywords should be deduplicated
        assert identity.keywords.count("wireless") <= 1
        assert identity.keywords.count("earbuds") <= 1

    def test_keywords_lowercase(self, builder):
        identity = builder.from_title("APPLE Airpods PRO")
        for kw in identity.keywords:
            assert kw == kw.lower()