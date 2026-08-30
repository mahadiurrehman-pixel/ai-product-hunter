"""
Tests for Robust Unit Normalization.

Covers all unit families, edge cases, ranges, approximations,
invalid values, false positives, and determinism.
"""
import pytest

from services.product_identity.units import (
    UnitConverter,
    UnitConversionResult,
)
from services.product_identity.attributes import (
    AttributeNormalizer,
    AttributeStatus,
)
from services.product_identity import ProductIdentityBuilder


# =============================================================================
# Storage Units
# =============================================================================

class TestStorageUnits:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_1tb_to_gb(self, conv):
        r = conv.convert_storage("1 TB")
        assert r.success
        assert r.numeric_value == 1024.0
        assert r.canonical_unit == "GB"
        assert r.original_unit == "TB"

    def test_1024gb(self, conv):
        r = conv.convert_storage("1024 GB")
        assert r.success
        assert r.numeric_value == 1024.0

    def test_500mb(self, conv):
        r = conv.convert_storage("500 MB")
        assert r.success
        assert r.numeric_value == pytest.approx(500 / 1024, rel=1e-3)

    def test_256gb(self, conv):
        r = conv.convert_storage("256GB")
        assert r.success
        assert r.numeric_value == 256.0

    def test_2tb(self, conv):
        r = conv.convert_storage("2TB")
        assert r.success
        assert r.numeric_value == 2048.0

    def test_1tib(self, conv):
        """IEC unit TiB treated as equivalent to TB for product listings."""
        r = conv.convert_storage("1 TiB")
        assert r.success
        assert r.numeric_value == 1024.0

    def test_1024mib(self, conv):
        r = conv.convert_storage("1024 MiB")
        assert r.success
        assert r.numeric_value == 1.0

    def test_raw_preserved(self, conv):
        r = conv.convert_storage("1 TB SSD")
        assert r.success
        assert r.numeric_value == 1024.0

    def test_comma_number(self, conv):
        r = conv.convert_storage("1,024 GB")
        assert r.success
        assert r.numeric_value == 1024.0


# =============================================================================
# Memory Units
# =============================================================================

class TestMemoryUnits:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_16gb(self, conv):
        r = conv.convert_storage("16GB")
        assert r.success
        assert r.numeric_value == 16.0

    def test_16384mb(self, conv):
        r = conv.convert_storage("16384 MB")
        assert r.success
        assert r.numeric_value == 16.0

    def test_8gb(self, conv):
        r = conv.convert_storage("8 GB")
        assert r.success
        assert r.numeric_value == 8.0


# =============================================================================
# Length / Size Units
# =============================================================================

class TestLengthUnits:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_1_inch_to_mm(self, conv):
        r = conv.convert_length("1 inch")
        assert r.success
        assert r.numeric_value == 25.4
        assert r.canonical_unit == "mm"

    def test_2_54_cm_to_mm(self, conv):
        r = conv.convert_length("2.54 cm")
        assert r.success
        assert r.numeric_value == 25.4

    def test_25_4_mm(self, conv):
        r = conv.convert_length("25.4 mm")
        assert r.success
        assert r.numeric_value == 25.4

    def test_15_6_inch(self, conv):
        r = conv.convert_length("15.6 inch")
        assert r.success
        assert r.numeric_value == 396.24

    def test_15_6_quote(self, conv):
        r = conv.convert_length('15.6"')
        assert r.success
        assert r.numeric_value == 396.24

    def test_39_624_cm(self, conv):
        r = conv.convert_length("39.624 cm")
        assert r.success
        assert abs(r.numeric_value - 396.24) < 0.01

    def test_1_meter(self, conv):
        r = conv.convert_length("1 m")
        assert r.success
        assert r.numeric_value == 1000.0

    def test_1_foot(self, conv):
        r = conv.convert_length("1 ft")
        assert r.success
        assert r.numeric_value == 304.8


# =============================================================================
# Weight Units
# =============================================================================

class TestWeightUnits:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_1kg_to_g(self, conv):
        r = conv.convert_weight("1 kg")
        assert r.success
        assert r.numeric_value == 1000.0
        assert r.canonical_unit == "g"

    def test_1000g(self, conv):
        r = conv.convert_weight("1000 g")
        assert r.success
        assert r.numeric_value == 1000.0

    def test_35_274_oz(self, conv):
        r = conv.convert_weight("35.274 oz")
        assert r.success
        assert abs(r.numeric_value - 1000.0) < 1.0

    def test_500mg(self, conv):
        r = conv.convert_weight("500 mg")
        assert r.success
        assert r.numeric_value == 0.5

    def test_2lb(self, conv):
        r = conv.convert_weight("2 lb")
        assert r.success
        assert abs(r.numeric_value - 907.184) < 0.01


# =============================================================================
# Volume Units
# =============================================================================

class TestVolumeUnits:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_1l_to_ml(self, conv):
        r = conv.convert_volume("1 L")
        assert r.success
        assert r.numeric_value == 1000.0
        assert r.canonical_unit == "ml"

    def test_1000ml(self, conv):
        r = conv.convert_volume("1000 ml")
        assert r.success
        assert r.numeric_value == 1000.0

    def test_500ml(self, conv):
        r = conv.convert_volume("500ml")
        assert r.success
        assert r.numeric_value == 500.0


# =============================================================================
# Battery Units
# =============================================================================

class TestBatteryUnits:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_5000mah(self, conv):
        r = conv.convert_battery("5000mAh")
        assert r.success
        assert r.numeric_value == 5000.0
        assert r.canonical_unit == "mAh"

    def test_5ah_to_mah(self, conv):
        r = conv.convert_battery("5Ah")
        assert r.success
        assert r.numeric_value == 5000.0

    def test_10000mah(self, conv):
        r = conv.convert_battery("10000 mAh")
        assert r.success
        assert r.numeric_value == 10000.0


# =============================================================================
# Power Units
# =============================================================================

class TestPowerUnits:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_1000w(self, conv):
        r = conv.convert_power("1000 W")
        assert r.success
        assert r.numeric_value == 1000.0
        assert r.canonical_unit == "W"

    def test_1kw_to_w(self, conv):
        r = conv.convert_power("1 kW")
        assert r.success
        assert r.numeric_value == 1000.0

    def test_20w(self, conv):
        r = conv.convert_power("20W")
        assert r.success
        assert r.numeric_value == 20.0

    def test_65_watts(self, conv):
        r = conv.convert_power("65 watts")
        assert r.success
        assert r.numeric_value == 65.0


# =============================================================================
# Voltage Units
# =============================================================================

class TestVoltageUnits:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_5v(self, conv):
        r = conv.convert_voltage("5V")
        assert r.success
        assert r.numeric_value == 5.0
        assert r.canonical_unit == "V"

    def test_5000mv_to_v(self, conv):
        r = conv.convert_voltage("5000mV")
        assert r.success
        assert r.numeric_value == 5.0


# =============================================================================
# Current Units
# =============================================================================

class TestCurrentUnits:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_1a(self, conv):
        r = conv.convert_current("1 A")
        assert r.success
        assert r.numeric_value == 1.0
        assert r.canonical_unit == "A"

    def test_1000ma_to_a(self, conv):
        r = conv.convert_current("1000mA")
        assert r.success
        assert r.numeric_value == 1.0


# =============================================================================
# Frequency Units
# =============================================================================

class TestFrequencyUnits:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_2400mhz(self, conv):
        r = conv.convert_frequency("2400 MHz")
        assert r.success
        assert r.numeric_value == 2400.0
        assert r.canonical_unit == "MHz"

    def test_2_4ghz_to_mhz(self, conv):
        r = conv.convert_frequency("2.4 GHz")
        assert r.success
        assert r.numeric_value == 2400.0


# =============================================================================
# Percentage
# =============================================================================

class TestPercentage:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_80_percent(self, conv):
        r = conv.convert_percent("80%")
        assert r.success
        assert r.numeric_value == 80.0
        assert r.canonical_unit == "%"

    def test_80_percent_word(self, conv):
        r = conv.convert_percent("80 percent")
        assert r.success
        assert r.numeric_value == 80.0


# =============================================================================
# Ranges
# =============================================================================

class TestRanges:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_10_to_20_kg(self, conv):
        r = conv.convert("10 to 20 kg", family="weight")
        assert r.success
        assert r.min_value == 10000.0
        assert r.max_value == 20000.0

    def test_10_dash_20_kg(self, conv):
        r = conv.convert("10-20 kg", family="weight")
        assert r.success
        assert r.min_value is not None
        assert r.max_value is not None
        assert r.min_value < r.max_value

    def test_10_en_dash_20_kg(self, conv):
        r = conv.convert("10–20 kg", family="weight")
        assert r.success
        assert r.min_value is not None


# =============================================================================
# Approximate Values
# =============================================================================

class TestApproximateValues:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_tilde_500g(self, conv):
        r = conv.convert("~500g", family="weight")
        assert r.success
        assert r.is_approximate is True
        assert r.numeric_value == 500.0

    def test_approximately_500g(self, conv):
        r = conv.convert("approximately 500g", family="weight")
        assert r.success
        assert r.is_approximate is True

    def test_about_500g(self, conv):
        r = conv.convert("about 500g", family="weight")
        assert r.success
        assert r.is_approximate is True

    def test_approx_500g(self, conv):
        r = conv.convert("approx. 500g", family="weight")
        assert r.success
        assert r.is_approximate is True

    def test_exact_not_approximate(self, conv):
        r = conv.convert("500g", family="weight")
        assert r.success
        assert r.is_approximate is False


# =============================================================================
# Invalid / Unknown Units
# =============================================================================

class TestInvalidUnits:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_unknown_unit(self, conv):
        r = conv.convert("15 foo")
        assert r.success is False
        assert r.numeric_value == 15.0
        assert r.original_unit == "foo"

    def test_malformed_number(self, conv):
        r = conv.convert("abc GB")
        assert r.success is False

    def test_empty_string(self, conv):
        r = conv.convert("")
        assert r.success is False

    def test_no_unit(self, conv):
        r = conv.convert("256")
        assert r.numeric_value == 256.0
        # No unit to convert, but number parsed
        assert r.success is False or r.canonical_unit is None


# =============================================================================
# False Positives
# =============================================================================

class TestFalsePositives:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_2nd_gen_not_unit(self, conv):
        r = conv.convert("2nd Gen")
        # Should not interpret as 2 units of anything
        assert r.success is False or r.numeric_value is None

    def test_usb_2_0_not_pack(self, conv):
        r = conv.convert("USB 2.0")
        assert r.success is False or r.canonical_unit is None

    def test_2026_not_measurement(self, conv):
        r = conv.convert("2026")
        # Just a number, no unit
        assert r.canonical_unit is None or r.success is False

    def test_6ft_cable(self, conv):
        r = conv.convert("6ft", family="length")
        assert r.success
        assert r.numeric_value == 1828.8  # 6 * 304.8


# =============================================================================
# Determinism
# =============================================================================

class TestDeterminism:
    @pytest.fixture
    def conv(self):
        return UnitConverter()

    def test_same_input_same_output(self, conv):
        r1 = conv.convert_storage("1 TB")
        r2 = conv.convert_storage("1 TB")
        assert r1.numeric_value == r2.numeric_value
        assert r1.canonical_unit == r2.canonical_unit

    def test_equivalent_values(self, conv):
        r1 = conv.convert_storage("1 TB")
        r2 = conv.convert_storage("1024 GB")
        assert r1.numeric_value == r2.numeric_value


# =============================================================================
# AttributeNormalizer Integration
# =============================================================================

class TestAttributeNormalizerIntegration:
    @pytest.fixture
    def norm(self):
        return AttributeNormalizer()

    def test_storage_with_unit_conversion(self, norm):
        r = norm.normalize_single("storage", "1 TB")
        assert r.numeric_value == 1024.0
        assert r.unit == "GB"
        assert r.original_unit == "TB"
        assert r.status == AttributeStatus.NORMALIZED

    def test_size_with_unit_conversion(self, norm):
        r = norm.normalize_single("size", "15.6 inch")
        assert r.numeric_value is not None
        assert r.unit == "mm"
        assert r.original_unit == "inch"

    def test_battery_with_unit_conversion(self, norm):
        r = norm.normalize_single("battery_capacity", "5Ah")
        assert r.numeric_value == 5000.0
        assert r.unit == "mAh"

    def test_wattage_with_unit_conversion(self, norm):
        r = norm.normalize_single("wattage", "1 kW")
        assert r.numeric_value == 1000.0
        assert r.unit == "W"

    def test_color_no_unit(self, norm):
        r = norm.normalize_single("color", "black")
        assert r.normalized_value == "black"
        assert r.unit is None

    def test_unknown_color_status(self, norm):
        r = norm.normalize_single("color", "Ocean Mist")
        assert r.status == AttributeStatus.UNKNOWN

    def test_original_unit_preserved(self, norm):
        r = norm.normalize_single("storage", "1 TB")
        assert r.raw_value == "1 TB"
        assert r.original_unit == "TB"
        assert r.unit == "GB"

    def test_approximate_preserved(self, norm):
        r = norm.normalize_single("weight", "~500g")
        assert r.is_approximate is True


# =============================================================================
# ProductIdentity Integration
# =============================================================================

class TestProductIdentityUnitIntegration:
    @pytest.fixture
    def builder(self):
        return ProductIdentityBuilder()

    def test_storage_canonical_in_identity(self, builder):
        identity = builder.from_title("Samsung Galaxy S24 Ultra 1TB")
        storage = identity.get_canonical_attribute("storage")
        assert storage is not None
        assert storage.numeric_value == 1024.0
        assert storage.unit == "GB"

    def test_memory_canonical_in_identity(self, builder):
        identity = builder.from_title("Laptop 16GB RAM 512GB SSD")
        memory = identity.get_canonical_attribute("memory")
        assert memory is not None
        assert memory.numeric_value == 16.0

    def test_flat_dict_backward_compat(self, builder):
        identity = builder.from_title("iPhone 15 256GB Black")
        assert isinstance(identity.attributes, dict)

    def test_canonical_attrs_have_original_unit(self, builder):
        identity = builder.from_title("Samsung Galaxy S24 Ultra 1TB")
        for attr in identity.canonical_attributes:
            if attr.numeric_value is not None and attr.unit:
                assert attr.original_unit is not None