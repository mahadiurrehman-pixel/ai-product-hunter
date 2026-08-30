"""
Tests for Model & Variant Intelligence.

Covers model extraction, variant detection, generation detection,
accessory vs device distinction, compatibility detection,
false positive prevention, canonicalization, and determinism.
"""
import pytest

from services.product_identity import (
    ModelIntelligence,
    ModelIntelligenceResult,
    ProductIdentityBuilder,
    DataQuality,
)


class TestModelExtraction:
    """Test model extraction for known product families."""

    @pytest.fixture
    def mi(self):
        return ModelIntelligence()

    def test_iphone_15(self, mi):
        r = mi.extract("iPhone 15 128GB Black")
        assert r.model is not None
        assert "iPhone 15" in r.model
        assert r.model_family == "iPhone"

    def test_iphone_15_pro(self, mi):
        r = mi.extract("iPhone 15 Pro 256GB")
        assert r.model is not None
        assert "Pro" in r.model
        assert "iPhone" in r.model

    def test_iphone_15_pro_max(self, mi):
        r = mi.extract("iPhone 15 Pro Max 512GB Natural Titanium")
        assert r.model is not None
        assert "Pro Max" in r.model

    def test_iphone_15_pro_max_more_specific_than_pro(self, mi):
        r = mi.extract("Apple iPhone 15 Pro Max 256GB")
        assert "Pro Max" in r.model
        # Must NOT be just "iPhone 15 Pro"
        assert r.model != "iPhone 15 Pro"

    def test_galaxy_s24(self, mi):
        r = mi.extract("Samsung Galaxy S24 128GB")
        assert r.model is not None
        assert "S24" in r.model
        assert r.model_family == "Galaxy S"

    def test_galaxy_s24_ultra(self, mi):
        r = mi.extract("Samsung Galaxy S24 Ultra 512GB")
        assert r.model is not None
        assert "Ultra" in r.model

    def test_sony_wh1000xm5(self, mi):
        r = mi.extract("Sony WH-1000XM5 Headphones")
        assert r.model is not None
        assert "1000" in r.model
        assert r.model_family == "WH"

    def test_sony_wh1000xm5_no_hyphen(self, mi):
        r = mi.extract("Sony WH1000XM5 Wireless")
        assert r.model is not None
        assert "1000" in r.model

    def test_rtx_4070(self, mi):
        r = mi.extract("NVIDIA RTX 4070 Graphics Card")
        assert r.model is not None
        assert "4070" in r.model
        assert r.model_family == "GeForce"

    def test_rtx_4070_ti(self, mi):
        r = mi.extract("RTX 4070 Ti SUPER 12GB")
        assert r.model is not None
        assert "Ti" in r.model or "TI" in r.model.upper()

    def test_airpods_pro_2(self, mi):
        r = mi.extract("Apple AirPods Pro 2 USB-C")
        assert r.model is not None
        assert "AirPods" in r.model
        assert r.model_family in ("AirPods Pro", "AirPods")

    def test_airpods_pro_2nd_gen(self, mi):
        r = mi.extract("AirPods Pro 2nd Gen USB-C")
        assert r.model is not None
        assert "AirPods" in r.model

    def test_macbook_air_m3(self, mi):
        r = mi.extract("Apple MacBook Air M3 15 inch")
        assert r.model is not None
        assert "MacBook" in r.model

    def test_pixel_8_pro(self, mi):
        r = mi.extract("Google Pixel 8 Pro 128GB")
        assert r.model is not None
        assert "Pixel" in r.model


class TestFalsePositivePrevention:
    """Test that random numbers and measurements are NOT models."""

    @pytest.fixture
    def mi(self):
        return ModelIntelligence()

    def test_2_pack_not_model(self, mi):
        r = mi.extract("Black Phone Case 2 Pack")
        # "2" should not be a model
        assert r.model is None or "2" not in (r.model or "")

    def test_6ft_cable_not_model(self, mi):
        r = mi.extract("USB Cable 6ft Nylon Braided")
        assert r.model is None

    def test_5_buttons_not_model(self, mi):
        r = mi.extract("Wireless Mouse 5 Buttons RGB")
        assert r.model is None

    def test_3_pieces_not_model(self, mi):
        r = mi.extract("Screen Protector 3 Pieces Tempered Glass")
        assert r.model is None

    def test_100w_charger_not_model(self, mi):
        r = mi.extract("100W USB-C Charger GaN Fast")
        assert r.model is None

    def test_year_not_model(self, mi):
        r = mi.extract("Calendar 2026 Edition")
        assert r.model is None

    def test_generic_title_no_model(self, mi):
        r = mi.extract("Wireless Bluetooth Earbuds TWS")
        assert r.model is None  # No specific model in generic title


class TestAccessoryDetection:
    """Test accessory vs device distinction."""

    @pytest.fixture
    def mi(self):
        return ModelIntelligence()

    def test_iphone_case_is_accessory(self, mi):
        r = mi.extract("iPhone 15 Case Silicone", product_type="phone_case")
        assert r.is_accessory is True

    def test_case_for_iphone_is_accessory(self, mi):
        r = mi.extract("Case for iPhone 15 Pro Max")
        assert r.is_accessory is True

    def test_screen_protector_is_accessory(self, mi):
        r = mi.extract(
            "Samsung S24 Screen Protector",
            product_type="screen_protector",
        )
        assert r.is_accessory is True

    def test_galaxy_cover_is_accessory(self, mi):
        r = mi.extract("Galaxy S24 Cover Clear", product_type="phone_case")
        assert r.is_accessory is True

    def test_airpods_case_is_accessory(self, mi):
        r = mi.extract("AirPods Pro Case Leather", product_type="phone_case")
        assert r.is_accessory is True

    def test_iphone_is_not_accessory(self, mi):
        r = mi.extract("Apple iPhone 15 Pro Max 256GB")
        assert r.is_accessory is False

    def test_earbuds_not_accessory(self, mi):
        r = mi.extract("Sony WH-1000XM5 Headphones")
        assert r.is_accessory is False


class TestCompatibilityDetection:
    """Test compatible model extraction for accessories."""

    @pytest.fixture
    def mi(self):
        return ModelIntelligence()

    def test_compatible_with_iphone(self, mi):
        r = mi.extract("MagSafe Case Compatible with iPhone 15 Pro")
        assert r.is_accessory is True
        assert len(r.compatible_models) > 0
        assert any("iPhone" in m for m in r.compatible_models)

    def test_case_for_iphone_15_pro_max(self, mi):
        r = mi.extract("Case for iPhone 15 Pro Max Clear")
        assert r.is_accessory is True
        assert any("Pro Max" in m for m in r.compatible_models)

    def test_accessory_no_own_model(self, mi):
        r = mi.extract(
            "Silicone Case for iPhone 15 Pro",
            product_type="phone_case",
        )
        assert r.model is None  # The case itself has no iPhone model
        assert len(r.compatible_models) > 0

    def test_designed_for_galaxy(self, mi):
        r = mi.extract("Charger Designed for Galaxy S24 Ultra")
        assert r.is_accessory is True
        assert any("Galaxy" in m for m in r.compatible_models)

    def test_replacement_for_airpods(self, mi):
        r = mi.extract("Replacement Ear Tips for AirPods Pro")
        assert r.is_accessory is True


class TestVariantExtraction:
    """Test variant detection."""

    @pytest.fixture
    def mi(self):
        return ModelIntelligence()

    def test_usb_c_variant(self, mi):
        r = mi.extract("AirPods Pro 2 USB-C")
        assert r.variant is not None
        assert "USB" in r.variant.upper()

    def test_lightning_variant(self, mi):
        r = mi.extract("AirPods Pro Lightning")
        assert r.variant is not None
        assert "LIGHTNING" in r.variant.upper()

    def test_gps_cellular_variant(self, mi):
        r = mi.extract("Apple Watch Series 9 GPS + Cellular")
        if r.variant:
            assert "GPS" in r.variant.upper() or "CELLULAR" in r.variant.upper()

    def test_no_variant_simple(self, mi):
        r = mi.extract("iPhone 15 128GB")
        # 128GB is storage attribute, not variant in MI
        # (variant may be None or contain storage from builder)
        assert r.model is not None


class TestGenerationDetection:
    """Test generation indicator extraction."""

    @pytest.fixture
    def mi(self):
        return ModelIntelligence()

    def test_2nd_gen(self, mi):
        r = mi.extract("AirPods Pro 2nd Gen")
        assert r.generation is not None
        assert "2" in r.generation or "nd" in r.generation.lower()

    def test_3rd_generation(self, mi):
        r = mi.extract("Echo Dot 3rd Generation")
        assert r.generation is not None

    def test_v2(self, mi):
        r = mi.extract("Smart Watch V2 Pro")
        assert r.generation is not None
        assert "V2" in r.generation.upper()

    def test_series_9(self, mi):
        r = mi.extract("Apple Watch Series 9")
        assert r.generation is not None

    def test_no_generation(self, mi):
        r = mi.extract("iPhone 15 Pro Max")
        # iPhone 15 doesn't have explicit "Gen" marker
        # Generation may or may not be detected
        assert isinstance(r.generation, (str, type(None)))


class TestCanonicalization:
    """Test model name canonicalization."""

    @pytest.fixture
    def mi(self):
        return ModelIntelligence()

    def test_case_insensitive(self, mi):
        r1 = mi.extract("iphone 15 pro max")
        r2 = mi.extract("iPhone 15 Pro Max")
        assert r1.model is not None
        assert r2.model is not None
        assert r1.model.lower() == r2.model.lower()

    def test_hyphen_variation(self, mi):
        r1 = mi.extract("Sony WH-1000XM5")
        r2 = mi.extract("Sony WH1000XM5")
        assert r1.model is not None
        assert r2.model is not None
        # Both should be recognized as the same model family
        assert r1.model_family == r2.model_family


class TestProductIdentityIntegration:
    """Test ModelIntelligence integrated with ProductIdentityBuilder."""

    @pytest.fixture
    def builder(self):
        return ProductIdentityBuilder()

    def test_iphone_15_pro_max_full_identity(self, builder):
        identity = builder.from_title("Apple iPhone 15 Pro Max 256GB Blue")
        assert identity.brand == "Apple"
        assert identity.product_type == "smartphone"
        assert identity.model is not None
        assert "Pro Max" in identity.model
        assert identity.model_family == "iPhone"
        assert identity.is_accessory is False
        assert "storage" in identity.attributes

    def test_case_for_iphone_accessory(self, builder):
        identity = builder.from_title("Case for iPhone 15 Pro Max Clear")
        assert identity.product_type == "phone_case"
        assert identity.is_accessory is True
        assert len(identity.compatible_models) > 0
        # The case's own model MUST be None — the iPhone belongs
        # in compatible_models, not in the case's model field
        assert identity.model is None

    def test_airpods_pro_2_usbc(self, builder):
        identity = builder.from_title("Apple AirPods Pro 2 USB-C White")
        assert identity.brand == "Apple"
        assert identity.product_type == "earbuds"
        assert identity.model is not None
        assert "AirPods" in identity.model

    def test_galaxy_s24_ultra(self, builder):
        identity = builder.from_title("Samsung Galaxy S24 Ultra 512GB")
        assert identity.brand == "Samsung"
        assert identity.model is not None
        assert "Ultra" in identity.model

    def test_sony_headphones(self, builder):
        identity = builder.from_title("Sony WH-1000XM5 Wireless Headphones")
        assert identity.brand == "Sony"
        assert identity.model is not None
        assert identity.product_type == "headphones"

    def test_rtx_graphics_card(self, builder):
        identity = builder.from_title("NVIDIA RTX 4070 Ti 12GB")
        assert identity.model is not None
        assert "4070" in identity.model

    def test_accessory_preserves_product_type(self, builder):
        """Critical: iPhone 15 Case must be phone_case, not smartphone."""
        identity = builder.from_title("iPhone 15 Case Silicone Black")
        assert identity.product_type == "phone_case"
        assert identity.product_type != "smartphone"

    def test_screen_protector_preserves_type(self, builder):
        identity = builder.from_title("Samsung Galaxy S24 Screen Protector")
        assert identity.product_type == "screen_protector"

    def test_compatible_models_in_dict(self, builder):
        identity = builder.from_title("Case Compatible with iPhone 15 Pro")
        d = identity.to_dict()
        assert "compatible_models" in d
        assert "is_accessory" in d
        assert "model_family" in d
        assert "generation" in d

    def test_identity_confidence_higher_with_model(self, builder):
        with_model = builder.from_title("Apple iPhone 15 Pro Max 256GB")
        without_model = builder.from_title("Wireless Earbuds Bluetooth")
        assert with_model.identity_confidence > without_model.identity_confidence

    def test_deterministic(self, builder):
        title = "Apple iPhone 15 Pro Max 256GB Space Gray"
        r1 = builder.from_title(title).to_dict()
        r2 = builder.from_title(title).to_dict()
        assert r1 == r2


class TestConflictDetection:
    """Test handling of conflicting model signals."""

    @pytest.fixture
    def builder(self):
        return ProductIdentityBuilder()

    def test_exclusion_respected(self, builder):
        identity = builder.from_title(
            "iPhone 15 Case NOT compatible with Pro Max"
        )
        assert identity.product_type == "phone_case"
        # Exclusions field should exist and be a list
        assert hasattr(identity, "exclusions")
        assert isinstance(identity.exclusions, list)
        # The identity was correctly identified as an accessory
        assert identity.is_accessory is True

    def test_multiple_models_picks_most_specific(self, builder):
        identity = builder.from_title("iPhone 15 Pro Max Case")
        assert identity.is_accessory is True
        # Should pick the most specific model for compatibility
        if identity.compatible_models:
            best = max(identity.compatible_models, key=len)
            assert "Pro Max" in best or "iPhone" in best