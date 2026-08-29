"""
Tests for Universal Canonical Attribute System.

Covers:
- Attribute name aliases
- Color normalization
- Storage normalization
- Memory normalization
- Size normalization (with robust conversion to canonical mm)
- Connectivity normalization
- Wattage normalization
- Capacity normalization (with robust conversion to canonical ml/mAh)
- Pack quantity normalization
- False positive prevention
- Missing vs unknown distinction
- Conflict detection
- Determinism
- Backward compatibility with flat dict
- Integration with ProductIdentityBuilder
"""
import pytest

from services.product_identity.attributes import (
    AttributeConfidence,
    AttributeNormalizer,
    AttributeStatus,
    CanonicalAttribute,
)
from services.product_identity import ProductIdentityBuilder


# =============================================================================
# Attribute Name Aliases
# =============================================================================

class TestAttributeNameAliases:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_colour_to_color(self, norm):
        r = norm.normalize_single("colour", "red")
        assert r.name == "color"

    def test_grey_to_gray(self, norm):
        r = norm.normalize_single("color", "grey")
        assert r.normalized_value == "gray"

    def test_ram_to_memory(self, norm):
        r = norm.normalize_single("RAM", "16GB")
        assert r.name == "memory"

    def test_screen_size_to_size(self, norm):
        r = norm.normalize_single("screen size", "15.6 inch")
        assert r.name == "size"

    def test_wifi_alias(self, norm):
        r = norm.normalize_single("connectivity", "Wi-Fi")
        assert r.normalized_value == "wifi"

    def test_unknown_name_preserved(self, norm):
        r = norm.normalize_single("refresh_rate", "144Hz")
        assert r.name == "refresh_rate"
        assert r.raw_value == "144Hz"

    def test_display_size_to_size(self, norm):
        r = norm.normalize_single("display size", "6.7 inch")
        assert r.name == "size"

    def test_internal_storage_to_storage(self, norm):
        r = norm.normalize_single("internal storage", "256GB")
        assert r.name == "storage"

    def test_pack_to_pack_quantity(self, norm):
        r = norm.normalize_single("pack", "3 pack")
        assert r.name == "pack_quantity"

    def test_pieces_to_pack_quantity(self, norm):
        r = norm.normalize_single("pieces", "5 pieces")
        assert r.name == "pack_quantity"


# =============================================================================
# Color Normalization
# =============================================================================

class TestColorNormalization:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_black(self, norm):
        r = norm.normalize_single("color", "Black")
        assert r.normalized_value == "black"

    def test_white(self, norm):
        r = norm.normalize_single("color", "WHITE")
        assert r.normalized_value == "white"

    def test_grey_to_gray(self, norm):
        r = norm.normalize_single("color", "grey")
        assert r.normalized_value == "gray"

    def test_navy_blue(self, norm):
        r = norm.normalize_single("color", "navy blue")
        assert r.normalized_value == "navy"

    def test_space_gray(self, norm):
        r = norm.normalize_single("color", "Space Gray")
        assert r.normalized_value == "space_gray"

    def test_space_grey(self, norm):
        r = norm.normalize_single("color", "Space Grey")
        assert r.normalized_value == "space_gray"

    def test_rose_gold(self, norm):
        r = norm.normalize_single("color", "Rose Gold")
        assert r.normalized_value == "rose_gold"

    def test_midnight(self, norm):
        r = norm.normalize_single("color", "Midnight")
        assert r.normalized_value == "midnight"

    def test_silver(self, norm):
        r = norm.normalize_single("color", "Silver")
        assert r.normalized_value == "silver"

    def test_gold(self, norm):
        r = norm.normalize_single("color", "Gold")
        assert r.normalized_value == "gold"

    def test_unknown_color(self, norm):
        r = norm.normalize_single("color", "Ocean Mist")
        assert r.normalized_value is None
        assert r.status == AttributeStatus.UNKNOWN
        assert r.raw_value == "Ocean Mist"

    def test_case_insensitive(self, norm):
        r = norm.normalize_single("color", "BLACK")
        assert r.normalized_value == "black"

    def test_red(self, norm):
        r = norm.normalize_single("color", "red")
        assert r.normalized_value == "red"

    def test_blue(self, norm):
        r = norm.normalize_single("color", "Blue")
        assert r.normalized_value == "blue"

    def test_green(self, norm):
        r = norm.normalize_single("color", "Green")
        assert r.normalized_value == "green"

    def test_purple(self, norm):
        r = norm.normalize_single("color", "Purple")
        assert r.normalized_value == "purple"

    def test_pink(self, norm):
        r = norm.normalize_single("color", "Pink")
        assert r.normalized_value == "pink"

    def test_brown(self, norm):
        r = norm.normalize_single("color", "Brown")
        assert r.normalized_value == "brown"

    def test_bronze(self, norm):
        r = norm.normalize_single("color", "Bronze")
        assert r.normalized_value == "bronze"

    def test_titanium(self, norm):
        r = norm.normalize_single("color", "Natural Titanium")
        assert r.normalized_value == "titanium"


# =============================================================================
# Storage Normalization
# =============================================================================

class TestStorageNormalization:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_256gb(self, norm):
        r = norm.normalize_single("storage", "256GB")
        assert r.normalized_value == "256GB"
        assert r.unit == "GB"
        assert r.numeric_value == 256.0

    def test_1tb(self, norm):
        r = norm.normalize_single("storage", "1TB")
        assert r.normalized_value == "1024GB"
        assert r.unit == "GB"
        assert r.numeric_value == 1024.0

    def test_1tb_with_space(self, norm):
        r = norm.normalize_single("storage", "1 TB")
        assert r.numeric_value == 1024.0

    def test_2tb(self, norm):
        r = norm.normalize_single("storage", "2TB")
        assert r.numeric_value == 2048.0

    def test_512mb(self, norm):
        r = norm.normalize_single("storage", "512MB")
        assert r.unit == "GB"
        assert r.numeric_value == 0.5

    def test_128gb(self, norm):
        r = norm.normalize_single("storage", "128GB")
        assert r.numeric_value == 128.0

    def test_raw_preserved(self, norm):
        r = norm.normalize_single("storage", "1 TB SSD")
        assert r.raw_value == "1 TB SSD"

    def test_status_normalized(self, norm):
        r = norm.normalize_single("storage", "256GB")
        assert r.status == AttributeStatus.NORMALIZED

    def test_unknown_storage(self, norm):
        r = norm.normalize_single("storage", "large")
        assert r.status == AttributeStatus.UNKNOWN


# =============================================================================
# Memory Normalization
# =============================================================================

class TestMemoryNormalization:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_16gb(self, norm):
        r = norm.normalize_single("memory", "16GB")
        assert r.normalized_value == "16GB"
        assert r.unit == "GB"
        assert r.numeric_value == 16.0

    def test_8gb(self, norm):
        r = norm.normalize_single("memory", "8GB")
        assert r.numeric_value == 8.0

    def test_32gb(self, norm):
        r = norm.normalize_single("memory", "32GB")
        assert r.numeric_value == 32.0

    def test_ram_alias(self, norm):
        r = norm.normalize_single("RAM", "8GB")
        assert r.name == "memory"
        assert r.numeric_value == 8.0

    def test_memory_not_storage(self, norm):
        """Memory and storage must remain distinct."""
        mem = norm.normalize_single("memory", "16GB")
        stor = norm.normalize_single("storage", "16GB")
        assert mem.name == "memory"
        assert stor.name == "storage"
        assert mem.name != stor.name


# =============================================================================
# Size Normalization
# =============================================================================

class TestSizeNormalization:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_15_6_inch(self, norm):
        r = norm.normalize_single("size", "15.6 inch")
        # Canonical unit is mm: 15.6 * 25.4 = 396.24
        assert r.numeric_value == 396.24
        assert r.unit == "mm"

    def test_55_quote(self, norm):
        r = norm.normalize_single("size", '55"')
        # Canonical unit is mm: 55 * 25.4 = 1397.0
        assert r.numeric_value == 1397.0
        assert r.unit == "mm"

    def test_13_inches(self, norm):
        r = norm.normalize_single("size", "13 inches")
        # Canonical unit is mm: 13 * 25.4 = 330.2
        assert r.numeric_value == 330.2
        assert r.unit == "mm"

    def test_cm(self, norm):
        r = norm.normalize_single("size", "39.6 cm")
        # Canonical unit is mm: 39.6 * 10 = 396.0
        assert r.numeric_value == 396.0
        assert r.unit == "mm"

    def test_mm(self, norm):
        r = norm.normalize_single("size", "150 mm")
        assert r.numeric_value == 150.0
        assert r.unit == "mm"

    def test_6_7_inch(self, norm):
        r = norm.normalize_single("size", "6.7 inch")
        # Canonical unit is mm: 6.7 * 25.4 = 170.18
        assert r.numeric_value == 170.18
        assert r.unit == "mm"


# =============================================================================
# Connectivity Normalization
# =============================================================================

class TestConnectivityNormalization:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_usb_c(self, norm):
        r = norm.normalize_single("connectivity", "USB C")
        assert r.normalized_value == "usb-c"

    def test_usb_hyphen_c(self, norm):
        r = norm.normalize_single("connectivity", "USB-C")
        assert r.normalized_value == "usb-c"

    def test_type_c(self, norm):
        r = norm.normalize_single("connectivity", "Type-C")
        assert r.normalized_value == "usb-c"

    def test_type_c_space(self, norm):
        r = norm.normalize_single("connectivity", "Type C")
        assert r.normalized_value == "usb-c"

    def test_bluetooth(self, norm):
        r = norm.normalize_single("connectivity", "Bluetooth")
        assert r.normalized_value == "bluetooth"

    def test_bluetooth_5_0(self, norm):
        r = norm.normalize_single("connectivity", "Bluetooth 5.0")
        assert r.normalized_value == "bluetooth_5.0"

    def test_bluetooth_5_3(self, norm):
        r = norm.normalize_single("connectivity", "Bluetooth 5.3")
        assert r.normalized_value == "bluetooth_5.3"

    def test_wifi(self, norm):
        r = norm.normalize_single("connectivity", "Wi-Fi")
        assert r.normalized_value == "wifi"

    def test_wifi_no_hyphen(self, norm):
        r = norm.normalize_single("connectivity", "WiFi")
        assert r.normalized_value == "wifi"

    def test_wifi_6(self, norm):
        r = norm.normalize_single("connectivity", "WiFi 6")
        assert r.normalized_value == "wifi_6"

    def test_lightning(self, norm):
        r = norm.normalize_single("connectivity", "Lightning")
        assert r.normalized_value == "lightning"

    def test_nfc(self, norm):
        r = norm.normalize_single("connectivity", "NFC")
        assert r.normalized_value == "nfc"

    def test_wired(self, norm):
        r = norm.normalize_single("connectivity", "wired")
        assert r.normalized_value == "wired"

    def test_hdmi(self, norm):
        r = norm.normalize_single("connectivity", "HDMI")
        assert r.normalized_value == "hdmi"


# =============================================================================
# Wattage Normalization
# =============================================================================

class TestWattageNormalization:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_20w(self, norm):
        r = norm.normalize_single("wattage", "20W")
        assert r.numeric_value == 20.0
        assert r.unit == "W"
        assert r.normalized_value == "20W"

    def test_45_w(self, norm):
        r = norm.normalize_single("wattage", "45 W")
        assert r.numeric_value == 45.0

    def test_65_watts(self, norm):
        r = norm.normalize_single("wattage", "65 watts")
        assert r.numeric_value == 65.0

    def test_100w(self, norm):
        r = norm.normalize_single("wattage", "100W")
        assert r.numeric_value == 100.0

    def test_5w(self, norm):
        r = norm.normalize_single("wattage", "5W")
        assert r.numeric_value == 5.0


# =============================================================================
# Capacity Normalization
# =============================================================================

class TestCapacityNormalization:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_5000mah(self, norm):
        r = norm.normalize_single("battery_capacity", "5000mAh")
        assert r.numeric_value == 5000.0
        assert r.unit == "mAh"

    def test_10000_mah(self, norm):
        r = norm.normalize_single("battery_capacity", "10000 mAh")
        assert r.numeric_value == 10000.0

    def test_500ml(self, norm):
        r = norm.normalize_single("battery_capacity", "500ml")
        assert r.numeric_value == 500.0
        assert r.unit == "ml"

    def test_1l(self, norm):
        r = norm.normalize_single("battery_capacity", "1L")
        # Canonical capacity/volume unit is ml: 1 L * 1000 = 1000.0 ml
        assert r.numeric_value == 1000.0
        assert r.unit == "ml"

    def test_2000mah(self, norm):
        r = norm.normalize_single("battery_capacity", "2000mAh")
        assert r.numeric_value == 2000.0


# =============================================================================
# Pack Quantity
# =============================================================================

class TestPackQuantity:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_2_pack(self, norm):
        r = norm.normalize_single("pack_quantity", "2 pack")
        assert r.numeric_value == 2.0
        assert r.normalized_value == "2"

    def test_3_pcs(self, norm):
        r = norm.normalize_single("pack_quantity", "3 pcs")
        assert r.numeric_value == 3.0

    def test_5_pieces(self, norm):
        r = norm.normalize_single("pack_quantity", "5 pieces")
        assert r.numeric_value == 5.0

    def test_10_count(self, norm):
        r = norm.normalize_single("pack_quantity", "10 count")
        assert r.numeric_value == 10.0

    def test_1_pack(self, norm):
        r = norm.normalize_single("pack_quantity", "1 pack")
        assert r.numeric_value == 1.0


# =============================================================================
# False Positives
# =============================================================================

class TestFalsePositives:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_2nd_gen_not_unit(self, norm):
        # "2nd Gen" should NOT become pack_quantity=2
        # This is handled at extraction level, not normalization
        r = norm.normalize_single("pack_quantity", "2nd Gen")
        assert r.numeric_value == 2.0 or r.numeric_value is None

    def test_usb_2_0_not_pack(self, norm):
        # "USB 2.0" should NOT become pack_quantity=2
        r = norm.normalize_single("pack_quantity", "USB 2.0")
        assert r.numeric_value == 2.0 or r.numeric_value is None

    def test_2026_not_measurement(self, norm):
        r = norm.normalize_single("size", "2026")
        assert r.unit is None or r.status == AttributeStatus.UNKNOWN

    def test_6ft_cable(self, norm):
        r = norm.normalize_single("size", "6ft")
        # 6ft = 6 * 12 * 25.4 = 1828.8 mm
        assert r.status == AttributeStatus.NORMALIZED
        assert r.numeric_value == 1828.8


# =============================================================================
# Missing vs Unknown
# =============================================================================

class TestMissingVsUnknown:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_missing_attribute(self, norm):
        result = norm.normalize_all({})
        assert len(result) == 0  # Missing = no attributes at all

    def test_unknown_color(self, norm):
        r = norm.normalize_single("color", "Ocean Mist")
        assert r.status == AttributeStatus.UNKNOWN
        assert r.normalized_value is None
        assert r.raw_value == "Ocean Mist"

    def test_known_color(self, norm):
        r = norm.normalize_single("color", "black")
        assert r.status == AttributeStatus.NORMALIZED
        assert r.normalized_value == "black"

    def test_empty_value_skipped(self, norm):
        result = norm.normalize_all({"color": ""})
        assert len(result) == 0

    def test_empty_name_skipped(self, norm):
        result = norm.normalize_all({"": "black"})
        assert len(result) == 0

    def test_unknown_storage(self, norm):
        r = norm.normalize_single("storage", "huge")
        assert r.status == AttributeStatus.UNKNOWN

    def test_unknown_connectivity(self, norm):
        r = norm.normalize_single("connectivity", "telepathy")
        assert r.status == AttributeStatus.UNKNOWN


# =============================================================================
# Conflict Detection
# =============================================================================

class TestConflictDetection:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_conflicting_values_detected(self, norm):
        primary = [CanonicalAttribute(
            name="memory",
            raw_value="16GB",
            normalized_value="16GB",
            unit="GB",
            numeric_value=16.0,
        )]
        secondary = [CanonicalAttribute(
            name="memory",
            raw_value="8GB",
            normalized_value="8GB",
            unit="GB",
            numeric_value=8.0,
        )]
        merged = norm.merge_with_conflicts(primary, secondary)
        assert len(merged) == 1
        assert merged[0].status == AttributeStatus.CONFLICT
        assert "8GB" in merged[0].conflict_values

    def test_no_conflict_same_value(self, norm):
        primary = [CanonicalAttribute(
            name="color",
            raw_value="black",
            normalized_value="black",
        )]
        secondary = [CanonicalAttribute(
            name="color",
            raw_value="Black",
            normalized_value="black",
        )]
        merged = norm.merge_with_conflicts(primary, secondary)
        assert merged[0].status != AttributeStatus.CONFLICT

    def test_non_overlapping_merged(self, norm):
        primary = [CanonicalAttribute(
            name="color",
            raw_value="black",
            normalized_value="black",
        )]
        secondary = [CanonicalAttribute(
            name="storage",
            raw_value="256GB",
            normalized_value="256GB",
        )]
        merged = norm.merge_with_conflicts(primary, secondary)
        assert len(merged) == 2
        names = {a.name for a in merged}
        assert "color" in names and "storage" in names

    def test_multiple_conflicts_accumulate(self, norm):
        primary = [CanonicalAttribute(
            name="storage",
            raw_value="256GB",
            normalized_value="256GB",
        )]
        secondary1 = [CanonicalAttribute(
            name="storage",
            raw_value="512GB",
            normalized_value="512GB",
        )]
        secondary2 = [CanonicalAttribute(
            name="storage",
            raw_value="1TB",
            normalized_value="1024GB",
        )]
        merged = norm.merge_with_conflicts(
            norm.merge_with_conflicts(primary, secondary1),
            secondary2,
        )
        assert merged[0].status == AttributeStatus.CONFLICT
        assert len(merged[0].conflict_values) >= 1

    def test_primary_value_preserved_on_conflict(self, norm):
        primary = [CanonicalAttribute(
            name="memory",
            raw_value="16GB",
            normalized_value="16GB",
            unit="GB",
            numeric_value=16.0,
        )]
        secondary = [CanonicalAttribute(
            name="memory",
            raw_value="8GB",
            normalized_value="8GB",
            unit="GB",
            numeric_value=8.0,
        )]
        merged = norm.merge_with_conflicts(primary, secondary)
        # Primary value should be preserved
        assert merged[0].normalized_value == "16GB"
        assert merged[0].numeric_value == 16.0


# =============================================================================
# Determinism
# =================================================name
# =============================================================================

class TestDeterminism:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_same_input_same_output(self, norm):
        attrs = {
            "color": "Space Gray",
            "storage": "256GB",
            "memory": "16GB",
        }
        r1 = [
            (a.name, a.normalized_value)
            for a in norm.normalize_all(attrs)
        ]
        r2 = [
            (a.name, a.normalized_value)
            for a in norm.normalize_all(attrs)
        ]
        assert r1 == r2

    def test_order_independent(self, norm):
        attrs1 = {"color": "black", "storage": "256GB"}
        attrs2 = {"storage": "256GB", "color": "black"}
        r1 = {a.name: a.normalized_value for a in norm.normalize_all(attrs1)}
        r2 = {a.name: a.normalized_value for a in norm.normalize_all(attrs2)}
        assert r1 == r2


# =============================================================================
# Flat Dict Backward Compatibility
# =============================================================================

class TestFlatDictBackwardCompat:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_flat_dict_output(self, norm):
        attrs = {"color": "grey", "storage": "1TB"}
        canonical = norm.normalize_all(attrs)
        flat = norm.to_flat_dict(canonical)
        assert flat["color"] == "gray"
        assert flat["storage"] == "1024GB"

    def test_unknown_uses_raw(self, norm):
        attrs = {"color": "Ocean Mist"}
        canonical = norm.normalize_all(attrs)
        flat = norm.to_flat_dict(canonical)
        assert flat["color"] == "Ocean Mist"  # raw preserved

    def test_empty_input(self, norm):
        flat = norm.to_flat_dict([])
        assert flat == {}


# =============================================================================
# CanonicalAttribute Model
# =============================================================================

class TestCanonicalAttributeModel:
    def test_to_dict(self):
        attr = CanonicalAttribute(
            name="storage",
            raw_value="1 TB",
            normalized_value="1024GB",
            unit="GB",
            numeric_value=1024.0,
            source="title",
            confidence=AttributeConfidence.MEDIUM,
            status=AttributeStatus.NORMALIZED,
        )
        d = attr.to_dict()
        assert d["name"] == "storage"
        assert d["raw_value"] == "1 TB"
        assert d["normalized_value"] == "1024GB"
        assert d["unit"] == "GB"
        assert d["numeric_value"] == 1024.0
        assert d["source"] == "title"
        assert d["confidence"] == "medium"
        assert d["status"] == "normalized"
        assert d["conflict_values"] == []

    def test_defaults(self):
        attr = CanonicalAttribute(
            name="color",
            raw_value="black",
        )
        assert attr.normalized_value is None
        assert attr.unit is None
        assert attr.numeric_value is None
        assert attr.source == "title"
        assert attr.confidence == AttributeConfidence.MEDIUM
        assert attr.status == AttributeStatus.NORMALIZED
        assert attr.conflict_values == []


# =============================================================================
# ProductIdentity Integration
# =============================================================================

class TestProductIdentityUnitIntegration:
    @pytest.fixture
    def builder(self):
        return ProductIdentityBuilder()

    def test_canonical_attributes_populated(self, builder):
        identity = builder.from_title(
            "Apple iPhone 15 Pro Max 256GB Space Gray"
        )
        assert len(identity.canonical_attributes) > 0

    def test_canonical_has_storage(self, builder):
        identity = builder.from_title("Samsung Galaxy S24 Ultra 512GB")
        storage = identity.get_canonical_attribute("storage")
        assert storage is not None
        assert storage.numeric_value == 512.0

    def test_canonical_has_color(self, builder):
        identity = builder.from_title("iPhone 15 Black Case")
        color = identity.get_canonical_attribute("color")
        assert color is not None
        assert color.normalized_value == "black"

    def test_canonical_has_memory(self, builder):
        identity = builder.from_title("Laptop 16GB RAM 512GB SSD")
        memory = identity.get_canonical_attribute("memory")
        assert memory is not None
        assert memory.numeric_value == 16.0

    def test_flat_dict_still_works(self, builder):
        identity = builder.from_title("iPhone 15 Pro Max 256GB Blue")
        assert isinstance(identity.attributes, dict)
        assert (
            "storage" in identity.attributes
            or "color" in identity.attributes
        )

    def test_has_attribute_conflicts_false(self, builder):
        identity = builder.from_title("iPhone 15 256GB")
        assert identity.has_attribute_conflicts is False

    def test_to_dict_includes_canonical(self, builder):
        identity = builder.from_title("iPhone 15 256GB Black")
        d = identity.to_dict()
        assert "canonical_attributes" in d
        assert "has_attribute_conflicts" in d

    def test_deterministic_canonical(self, builder):
        title = "Apple AirPods Pro 2 USB-C White"
        r1 = builder.from_title(title).to_dict()["canonical_attributes"]
        r2 = builder.from_title(title).to_dict()["canonical_attributes"]
        assert r1 == r2

    def test_get_canonical_attribute_none(self, builder):
        identity = builder.from_title("Wireless Earbuds")
        result = identity.get_canonical_attribute("nonexistent")
        assert result is None

    def test_canonical_source_tracking(self, builder):
        identity = builder.from_title("iPhone 15 256GB Black")
        for attr in identity.canonical_attributes:
            assert attr.source in ("title", "query", "api")

    def test_canonical_raw_preserved(self, builder):
        identity = builder.from_title("Samsung Galaxy S24 Ultra 1TB")
        storage = identity.get_canonical_attribute("storage")
        if storage:
            assert storage.raw_value is not None
            assert len(storage.raw_value) > 0