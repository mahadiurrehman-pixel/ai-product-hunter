"""
Robust Unit Normalization Engine.

Provides deterministic unit parsing, conversion, and normalization
for product attribute values. Integrates with the Universal Canonical
Attribute System.

Design rules:
- Rule-based only, no AI/LLM
- Deterministic: same input → same output
- Raw values ALWAYS preserved
- Unknown units → status=UNKNOWN, no guessing
- Ranges preserved as min/max, not collapsed to midpoint
- Approximate values flagged, not silently made exact

Canonical unit policy (documented per family):
- Storage:  GB  (binary: 1 TB = 1024 GB)
- Memory:   GB  (binary: 1 TB = 1024 GB)
- Length:   mm  (avoids floating-point inch fractions)
- Weight:   g   (grams)
- Volume:   ml  (milliliters)
- Battery:  mAh (milliamp-hours)
- Power:    W   (watts)
- Voltage:  V   (volts)
- Current:  A   (amperes)
- Frequency: MHz (megahertz)
- Time:     s   (seconds)
- Percent:  %   (0-100 scale, not 0-1)

Storage/Memory binary policy:
  1 KB = 1024 B
  1 MB = 1024 KB
  1 GB = 1024 MB
  1 TB = 1024 GB
  IEC units (KiB, MiB, GiB, TiB) are treated as equivalent to
  their SI counterparts for product listing purposes, since
  manufacturers and marketplaces use them interchangeably.
  The raw_value always preserves the original unit string.
"""
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# Conversion Result
# =============================================================================

@dataclass
class UnitConversionResult:
    """
    Result of a unit parsing and conversion operation.

    Fields:
        numeric_value: Parsed and converted numeric value
        canonical_unit: Target unit after conversion
        original_unit: Unit as found in the raw input
        is_approximate: Whether the raw value was marked approximate
        min_value: Lower bound for range values
        max_value: Upper bound for range values
        success: Whether conversion succeeded
    """

    numeric_value: Optional[float] = None
    canonical_unit: Optional[str] = None
    original_unit: Optional[str] = None
    is_approximate: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    success: bool = False


# =============================================================================
# Unit Aliases — Centralized
# =============================================================================

# Maps all known unit strings to their canonical form
# Format: {alias: canonical_unit}
UNIT_ALIASES = {
    # Storage / Memory (canonical: GB)
    "b": "B", "byte": "B", "bytes": "B",
    "kb": "KB", "kilobyte": "KB", "kilobytes": "KB",
    "kib": "KB",
    "mb": "MB", "megabyte": "MB", "megabytes": "MB",
    "mib": "MB",
    "gb": "GB", "gigabyte": "GB", "gigabytes": "GB",
    "gib": "GB",
    "tb": "TB", "terabyte": "TB", "terabytes": "TB",
    "tib": "TB",

    # Length (canonical: mm)
    "mm": "mm", "millimeter": "mm", "millimeters": "mm",
    "cm": "cm", "centimeter": "cm", "centimeters": "cm",
    "m": "m", "meter": "m", "meters": "m", "metre": "m", "metres": "m",
    "in": "inch", "inch": "inch", "inches": "inch", '"': "inch",
    "ft": "ft", "foot": "ft", "feet": "ft",
    "yd": "yd", "yard": "yd", "yards": "yd",

    # Weight (canonical: g)
    "mg": "mg", "milligram": "mg", "milligrams": "mg",
    "g": "g", "gram": "g", "grams": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "oz": "oz", "ounce": "oz", "ounces": "oz",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb",

    # Volume (canonical: ml)
    "ml": "ml", "milliliter": "ml", "milliliters": "ml",
    "millilitre": "ml", "millilitres": "ml",
    "l": "L", "liter": "L", "liters": "L",
    "litre": "L", "litres": "L",
    "fl oz": "fl_oz", "floz": "fl_oz", "fluid ounce": "fl_oz",

    # Battery (canonical: mAh)
    "mah": "mAh", "milliamp-hour": "mAh", "milliamp-hours": "mAh",
    "ah": "Ah", "amp-hour": "Ah", "amp-hours": "Ah",

    # Power (canonical: W)
    "w": "W", "watt": "W", "watts": "W",
    "kw": "kW", "kilowatt": "kW", "kilowatts": "kW",

    # Voltage (canonical: V)
    "v": "V", "volt": "V", "volts": "V",
    "mv": "mV", "millivolt": "mV", "millivolts": "mV",
    "kv": "kV", "kilovolt": "kV", "kilovolts": "kV",

    # Current (canonical: A)
    "a": "A", "amp": "A", "amps": "A", "ampere": "A", "amperes": "A",
    "ma": "mA", "milliamp": "mA", "milliamps": "mA",

    # Frequency (canonical: MHz)
    "hz": "Hz", "hertz": "Hz",
    "khz": "kHz", "kilohertz": "kHz",
    "mhz": "MHz", "megahertz": "MHz",
    "ghz": "GHz", "gigahertz": "GHz",

    # Time (canonical: s)
    "ms": "ms", "millisecond": "ms", "milliseconds": "ms",
    "s": "s", "sec": "s", "second": "s", "seconds": "s",
    "min": "min", "minute": "min", "minutes": "min",
    "h": "h", "hr": "h", "hour": "h", "hours": "h",

    # Percentage (canonical: %)
    "%": "%", "percent": "%", "pct": "%",
}


# =============================================================================
# Conversion Factors to Canonical Unit
# =============================================================================

# Storage/Memory → GB (binary: 1024-based)
STORAGE_TO_GB = {
    "B": 1 / (1024 ** 3),
    "KB": 1 / (1024 ** 2),
    "MB": 1 / 1024,
    "GB": 1.0,
    "TB": 1024.0,
}

# Length → mm
LENGTH_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "inch": 25.4,
    "ft": 304.8,
    "yd": 914.4,
}

# Weight → g
WEIGHT_TO_G = {
    "mg": 0.001,
    "g": 1.0,
    "kg": 1000.0,
    "oz": 28.3495,
    "lb": 453.592,
}

# Volume → ml
VOLUME_TO_ML = {
    "ml": 1.0,
    "L": 1000.0,
    "fl_oz": 29.5735,  # US fluid ounce
}

# Battery → mAh
BATTERY_TO_MAH = {
    "mAh": 1.0,
    "Ah": 1000.0,
}

# Power → W
POWER_TO_W = {
    "W": 1.0,
    "kW": 1000.0,
}

# Voltage → V
VOLTAGE_TO_V = {
    "mV": 0.001,
    "V": 1.0,
    "kV": 1000.0,
}

# Current → A
CURRENT_TO_A = {
    "mA": 0.001,
    "A": 1.0,
}

# Frequency → MHz
FREQUENCY_TO_MHZ = {
    "Hz": 0.000001,
    "kHz": 0.001,
    "MHz": 1.0,
    "GHz": 1000.0,
}

# Time → s
TIME_TO_S = {
    "ms": 0.001,
    "s": 1.0,
    "min": 60.0,
    "h": 3600.0,
}


# =============================================================================
# Unit Family Mapping
# =============================================================================

# Maps canonical unit → (conversion_table, family_name, canonical_unit_name)
UNIT_FAMILY = {}
for unit in STORAGE_TO_GB:
    UNIT_FAMILY[unit] = (STORAGE_TO_GB, "storage", "GB")
for unit in LENGTH_TO_MM:
    UNIT_FAMILY[unit] = (LENGTH_TO_MM, "length", "mm")
for unit in WEIGHT_TO_G:
    UNIT_FAMILY[unit] = (WEIGHT_TO_G, "weight", "g")
for unit in VOLUME_TO_ML:
    UNIT_FAMILY[unit] = (VOLUME_TO_ML, "volume", "ml")
for unit in BATTERY_TO_MAH:
    UNIT_FAMILY[unit] = (BATTERY_TO_MAH, "battery", "mAh")
for unit in POWER_TO_W:
    UNIT_FAMILY[unit] = (POWER_TO_W, "power", "W")
for unit in VOLTAGE_TO_V:
    UNIT_FAMILY[unit] = (VOLTAGE_TO_V, "voltage", "V")
for unit in CURRENT_TO_A:
    UNIT_FAMILY[unit] = (CURRENT_TO_A, "current", "A")
for unit in FREQUENCY_TO_MHZ:
    UNIT_FAMILY[unit] = (FREQUENCY_TO_MHZ, "frequency", "MHz")
for unit in TIME_TO_S:
    UNIT_FAMILY[unit] = (TIME_TO_S, "time", "s")


# =============================================================================
# Parsing Patterns
# =============================================================================

# Approximate indicators
APPROX_PATTERN = re.compile(
    r"^(?:~|approx\.?|approximately|about|around)\s*",
    re.IGNORECASE,
)

# Range patterns: "10-20 kg", "10 to 20 kg", "10–20 kg"
RANGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:[-–—]|to)\s*(\d+(?:\.\d+)?)\s*([a-z%\"']*)",
    re.IGNORECASE,
)

# Number + unit pattern
# Handles: "256GB", "1 TB", "15.6 inch", "5,000 mAh", "100W", "1024 GB"
NUMBER_UNIT_PATTERN = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)\s*"
    r"([a-z%\"']*)",
    re.IGNORECASE,
)


# =============================================================================
# Unit Converter
# =============================================================================

class UnitConverter:
    """
    Parses and converts unit-bearing values to canonical form.

    Usage:
        converter = UnitConverter()
        result = converter.convert("1 TB", family="storage")
        # result.numeric_value = 1024.0
        # result.canonical_unit = "GB"
        # result.original_unit = "TB"

    The converter:
    1. Strips approximate indicators (~, approx, about)
    2. Detects ranges (10-20 kg)
    3. Parses number + unit
    4. Resolves unit aliases
    5. Applies conversion factors
    6. Returns structured result
    """

    # Precision: round to 4 decimal places to avoid floating-point noise
    PRECISION = 4

    def convert(
        self,
        raw_value: str,
        family: Optional[str] = None,
    ) -> UnitConversionResult:
        """
        Parse and convert a raw value string.

        Args:
            raw_value: Raw string like "1 TB", "15.6 inch", "~500g"
            family: Optional unit family hint (storage, length, etc.)

        Returns:
            UnitConversionResult with parsed and converted values
        """
        if not raw_value or not raw_value.strip():
            return UnitConversionResult()

        text = raw_value.strip()

        # Step 1: Detect approximate
        is_approx = False
        approx_match = APPROX_PATTERN.match(text)
        if approx_match:
            is_approx = True
            text = text[approx_match.end():].strip()

        # Step 2: Detect range
        range_match = RANGE_PATTERN.search(text)
        if range_match:
            return self._convert_range(
                range_match, text, is_approx, family
            )

        # Step 3: Parse number + unit
        num, unit_str = self._parse_number_unit(text)
        if num is None:
            return UnitConversionResult(is_approximate=is_approx)

        # Step 4: Resolve unit alias
        canonical_unit = self._resolve_unit(unit_str, family)
        if canonical_unit is None:
            # Unknown unit — preserve raw, no conversion
            return UnitConversionResult(
                numeric_value=num,
                original_unit=unit_str,
                is_approximate=is_approx,
                success=False,
            )

        # Step 5: Convert
        converted = self._apply_conversion(num, canonical_unit)

        return UnitConversionResult(
            numeric_value=converted,
            canonical_unit=self._get_canonical_unit_name(canonical_unit),
            original_unit=canonical_unit,
            is_approximate=is_approx,
            success=True,
        )

    def convert_storage(self, raw_value: str) -> UnitConversionResult:
        """Convert storage/memory value to GB."""
        return self.convert(raw_value, family="storage")

    def convert_length(self, raw_value: str) -> UnitConversionResult:
        """Convert length value to mm."""
        return self.convert(raw_value, family="length")

    def convert_weight(self, raw_value: str) -> UnitConversionResult:
        """Convert weight value to g."""
        return self.convert(raw_value, family="weight")

    def convert_volume(self, raw_value: str) -> UnitConversionResult:
        """Convert volume value to ml."""
        return self.convert(raw_value, family="volume")

    def convert_battery(self, raw_value: str) -> UnitConversionResult:
        """Convert battery capacity to mAh."""
        return self.convert(raw_value, family="battery")

    def convert_power(self, raw_value: str) -> UnitConversionResult:
        """Convert power value to W."""
        return self.convert(raw_value, family="power")

    def convert_voltage(self, raw_value: str) -> UnitConversionResult:
        """Convert voltage to V."""
        return self.convert(raw_value, family="voltage")

    def convert_current(self, raw_value: str) -> UnitConversionResult:
        """Convert current to A."""
        return self.convert(raw_value, family="current")

    def convert_frequency(self, raw_value: str) -> UnitConversionResult:
        """Convert frequency to MHz."""
        return self.convert(raw_value, family="frequency")

    def convert_time(self, raw_value: str) -> UnitConversionResult:
        """Convert time to s."""
        return self.convert(raw_value, family="time")

    def convert_percent(self, raw_value: str) -> UnitConversionResult:
        """Parse percentage value."""
        text = raw_value.strip().lower()
        is_approx = False
        approx_match = APPROX_PATTERN.match(text)
        if approx_match:
            is_approx = True
            text = text[approx_match.end():].strip()

        num, _ = self._parse_number_unit(text)
        if num is None:
            return UnitConversionResult(is_approximate=is_approx)

        return UnitConversionResult(
            numeric_value=num,
            canonical_unit="%",
            original_unit="%",
            is_approximate=is_approx,
            success=True,
        )

    def _parse_number_unit(
        self, text: str
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Parse a number and unit from text.

        Returns:
            (numeric_value, unit_string) or (None, None)
        """
        match = NUMBER_UNIT_PATTERN.search(text)
        if not match:
            return None, None

        num_str = match.group(1).replace(",", "")
        unit_str = (match.group(2) or "").strip().lower()

        try:
            num = float(num_str)
        except (ValueError, TypeError):
            return None, None

        return num, unit_str if unit_str else None

    def _resolve_unit(
        self,
        unit_str: Optional[str],
        family: Optional[str] = None,
    ) -> Optional[str]:
        """
        Resolve a unit string to its canonical alias key.

        Args:
            unit_str: Raw unit string (e.g., "gb", "inch", "w")
            family: Optional family hint for disambiguation

        Returns:
            Canonical unit key from UNIT_ALIASES, or None if unknown
        """
        if not unit_str:
            return None

        key = unit_str.strip().lower()

        # Direct lookup
        if key in UNIT_ALIASES:
            return UNIT_ALIASES[key]

        # Try with quote handling
        if key in ('"', "'", "in"):
            return UNIT_ALIASES.get(key)

        return None

    def _apply_conversion(
        self,
        value: float,
        canonical_unit: str,
    ) -> Optional[float]:
        """
        Apply conversion factor to normalize value.

        Returns:
            Converted numeric value, or None if no conversion available
        """
        if canonical_unit not in UNIT_FAMILY:
            return value

        table, _, _ = UNIT_FAMILY[canonical_unit]
        factor = table.get(canonical_unit, 1.0)

        try:
            result = Decimal(str(value)) * Decimal(str(factor))
            # Round to PRECISION decimal places
            result = float(
                result.quantize(
                    Decimal(10) ** -self.PRECISION,
                    rounding=ROUND_HALF_UP,
                )
            )
            # Clean up trailing zeros
            if result == int(result):
                return float(int(result))
            return result
        except (InvalidOperation, OverflowError):
            return value

    def _get_canonical_unit_name(self, canonical_unit: str) -> str:
        """Get the canonical unit name for a resolved unit."""
        if canonical_unit in UNIT_FAMILY:
            _, _, canon_name = UNIT_FAMILY[canonical_unit]
            return canon_name
        return canonical_unit

    def _convert_range(
        self,
        match: re.Match,
        full_text: str,
        is_approx: bool,
        family: Optional[str],
    ) -> UnitConversionResult:
        """Convert a range value like '10-20 kg'."""
        try:
            min_val = float(match.group(1))
            max_val = float(match.group(2))
            unit_str = match.group(3).strip().lower()
        except (ValueError, TypeError):
            return UnitConversionResult(is_approximate=is_approx)

        canonical_unit = self._resolve_unit(unit_str, family)
        if canonical_unit is None:
            return UnitConversionResult(
                numeric_value=min_val,
                original_unit=unit_str,
                is_approximate=is_approx,
                min_value=min_val,
                max_value=max_val,
                success=False,
            )

        min_converted = self._apply_conversion(min_val, canonical_unit)
        max_converted = self._apply_conversion(max_val, canonical_unit)

        return UnitConversionResult(
            numeric_value=min_converted,  # Use min as primary
            canonical_unit=self._get_canonical_unit_name(canonical_unit),
            original_unit=canonical_unit,
            is_approximate=is_approx,
            min_value=min_converted,
            max_value=max_converted,
            success=True,
        )