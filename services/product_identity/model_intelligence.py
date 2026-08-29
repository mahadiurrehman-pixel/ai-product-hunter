"""
Model and Variant Intelligence for Product Identity.

Strengthens deterministic extraction of:
- Product model (iPhone 15 Pro Max, Galaxy S24 Ultra, WH-1000XM5)
- Model family (iPhone, Galaxy S, AirPods Pro)
- Generation (2nd Gen, V2, Mk II)
- Variant (USB-C, Lightning, GPS + Cellular)
- Compatible models (for accessories: "Case for iPhone 15 Pro Max")

Design rules:
- Rule-based only, no AI/LLM
- Deterministic: same input → same output
- Accessory-aware: "iPhone 15 Case" does NOT get model="iPhone 15"
- False-positive protected: "2 pack", "6ft", "5 buttons" are NOT models
- Preserves specificity: "iPhone 15 Pro Max" ≠ "iPhone 15"
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ModelIntelligenceResult:
    """
    Output of model/variant intelligence extraction.

    Fields:
        model: Full specific model identifier (e.g., "iPhone 15 Pro Max")
        model_family: Product family (e.g., "iPhone", "Galaxy S", "AirPods Pro")
        generation: Generation indicator (e.g., "2nd Gen", "V2")
        variant: Configuration variant (e.g., "USB-C", "GPS + Cellular")
        compatible_models: Models this product is compatible with (accessories)
        is_accessory: Whether the product is an accessory for another device
        confidence: 0.0-1.0 confidence in model extraction quality
    """

    model: Optional[str] = None
    model_family: Optional[str] = None
    generation: Optional[str] = None
    variant: Optional[str] = None
    compatible_models: List[str] = field(default_factory=list)
    is_accessory: bool = False
    confidence: float = 0.0


# =============================================================================
# Accessory context patterns
# =============================================================================

# Phrases that indicate the product is an accessory FOR another device
ACCESSORY_FOR_PATTERNS = [
    re.compile(r"\b(?:case|cover|protector|skin|shell)\s+for\b", re.IGNORECASE),
    re.compile(r"\b(?:compatible|works)\s+with\b", re.IGNORECASE),
    re.compile(r"\b(?:designed|made)\s+for\b", re.IGNORECASE),
    re.compile(r"\breplacement\s+for\b", re.IGNORECASE),
    re.compile(r"\b(?:charger|cable|adapter|dock|stand|holder|mount)\s+for\b", re.IGNORECASE),
    re.compile(r"\bfor\s+(?:iphone|ipad|galaxy|pixel|airpods|macbook|surface)\b", re.IGNORECASE),
]

# Product types that are inherently accessories
ACCESSORY_PRODUCT_TYPES = {
    "phone_case", "screen_protector", "charger", "cable",
    "adapter", "power_bank",
}


# =============================================================================
# Model extraction patterns
#
# Order matters: more specific patterns first to prevent partial matches.
# Each tuple: (compiled_regex, model_family_name, brand_hint)
# =============================================================================

MODEL_PATTERNS: List[Tuple[re.Pattern, str, Optional[str]]] = [
    # --- Apple iPhone (most specific first) ---
    (
        re.compile(
            r"\b(iPhone\s+\d+\s+Pro\s+Max)\b", re.IGNORECASE
        ),
        "iPhone", "Apple",
    ),
    (
        re.compile(
            r"\b(iPhone\s+\d+\s+Pro)\b", re.IGNORECASE
        ),
        "iPhone", "Apple",
    ),
    (
        re.compile(
            r"\b(iPhone\s+\d+\s+(?:Plus|SE|Mini))\b", re.IGNORECASE
        ),
        "iPhone", "Apple",
    ),
    (
        re.compile(
            r"\b(iPhone\s+\d+)\b", re.IGNORECASE
        ),
        "iPhone", "Apple",
    ),

    # --- Apple AirPods ---
    (
        re.compile(
            r"\b(AirPods\s+Pro\s+Max)\b", re.IGNORECASE
        ),
        "AirPods", "Apple",
    ),
    (
        re.compile(
            r"\b(AirPods\s+Pro(?:\s+\d+(?:st|nd|rd|th)?\s*(?:Gen(?:eration)?)?)?)\b",
            re.IGNORECASE,
        ),
        "AirPods Pro", "Apple",
    ),
    (
        re.compile(
            r"\b(AirPods(?:\s+\d+(?:st|nd|rd|th)?\s*(?:Gen(?:eration)?)?)?)\b",
            re.IGNORECASE,
        ),
        "AirPods", "Apple",
    ),

    # --- Apple Watch ---
    (
        re.compile(
            r"\b(Apple\s+Watch\s+(?:Ultra\s+\d*|SE\s*\d*|Series\s+\d+))\b",
            re.IGNORECASE,
        ),
        "Apple Watch", "Apple",
    ),

    # --- Apple MacBook ---
    (
        re.compile(
            r"\b(MacBook\s+(?:Air|Pro)(?:\s+M\d+)?)\b", re.IGNORECASE
        ),
        "MacBook", "Apple",
    ),

    # --- Samsung Galaxy S (most specific first) ---
    (
        re.compile(
            r"\b(Galaxy\s+S\d+\s+(?:Ultra|Plus|FE))\b", re.IGNORECASE
        ),
        "Galaxy S", "Samsung",
    ),
    (
        re.compile(
            r"\b(Galaxy\s+S\d+)\b", re.IGNORECASE
        ),
        "Galaxy S", "Samsung",
    ),

    # --- Samsung Galaxy Z ---
    (
        re.compile(
            r"\b(Galaxy\s+Z\s+(?:Fold|Flip)\d*)\b", re.IGNORECASE
        ),
        "Galaxy Z", "Samsung",
    ),

    # --- Samsung Galaxy A ---
    (
        re.compile(
            r"\b(Galaxy\s+A\d+(?:\s+\d+G)?)\b", re.IGNORECASE
        ),
        "Galaxy A", "Samsung",
    ),

    # --- Samsung Galaxy Tab ---
    (
        re.compile(
            r"\b(Galaxy\s+Tab\s+S?\d+(?:\s+(?:Ultra|Plus|FE))?)\b",
            re.IGNORECASE,
        ),
        "Galaxy Tab", "Samsung",
    ),

    # --- Sony Headphones ---
    (
        re.compile(
            r"\b(WH-?\d{3,4}[A-Z]{0,2}\d*)\b", re.IGNORECASE
        ),
        "WH", "Sony",
    ),
    (
        re.compile(
            r"\b(WF-?\d{3,4}[A-Z]{0,2}\d*)\b", re.IGNORECASE
        ),
        "WF", "Sony",
    ),

    # --- NVIDIA GPU ---
    (
        re.compile(
            r"\b((?:RTX|GTX)\s*\d{4}(?:\s*Ti)?(?:\s*SUPER)?)\b",
            re.IGNORECASE,
        ),
        "GeForce", "Nvidia",
    ),

    # --- AMD GPU ---
    (
        re.compile(
            r"\b(RX\s*\d{4}\s*(?:XT|XTX)?)\b", re.IGNORECASE
        ),
        "Radeon RX", "AMD",
    ),

    # --- Lenovo ThinkPad ---
    (
        re.compile(
            r"\b(ThinkPad\s+[A-Z]\d+(?:\s+[A-Za-z]+)?)\b", re.IGNORECASE
        ),
        "ThinkPad", "Lenovo",
    ),

    # --- Google Pixel ---
    (
        re.compile(
            r"\b(Pixel\s+\d+[a-z]?(?:\s+(?:Pro|XL|Fold|a))?)\b",
            re.IGNORECASE,
        ),
        "Pixel", "Google",
    ),
]


# =============================================================================
# Generation patterns
# =============================================================================

GENERATION_PATTERNS = [
    re.compile(r"\b(\d+(?:st|nd|rd|th)\s*Gen(?:eration)?)\b", re.IGNORECASE),
    re.compile(r"\bGen(?:eration)?\s*(\d+)\b", re.IGNORECASE),
    re.compile(r"\b(V\d+)\b", re.IGNORECASE),
    re.compile(r"\b(Mk\s*(?:II|III|IV|V|2|3|4|5))\b", re.IGNORECASE),
    re.compile(r"\bMark\s*(?:II|III|IV|V|2|3|4|5)\b", re.IGNORECASE),
    re.compile(r"\bSeries\s*(\d+)\b", re.IGNORECASE),
]


# =============================================================================
# False positive protection
# =============================================================================

# Tokens that look like model numbers but are NOT
FALSE_POSITIVE_CONTEXTS = re.compile(
    r"\b\d+\s*(?:pack|pcs|pieces|count|ct|ft|inch|inches|cm|mm|buttons|"
    r"ports|keys|w|watt|watts|mah|ml|oz|lbs|kg|gb|tb|mb|"
    r"led|leds|usb|hdmi|speed|rpm|fps|hz|khz|mhz|ghz)\b",
    re.IGNORECASE,
)

# Standalone years are not models
YEAR_PATTERN = re.compile(r"\b(20[12]\d)\b")

# Single digits are not models
SINGLE_DIGIT = re.compile(r"^\d$")


# =============================================================================
# Variant connectivity markers
# =============================================================================

VARIANT_CONNECTIVITY = {
    "usb-c", "usb c", "lightning", "wifi", "wi-fi",
    "5g", "4g", "lte", "bluetooth", "wired", "wireless",
    "gps", "cellular", "gps + cellular", "wifi + cellular",
}


class ModelIntelligence:
    """
    Extracts and refines model, variant, generation, and compatibility
    information from product titles.

    Designed to run AFTER QueryParser and ProductNormalizer, refining
    their output with deeper model-specific intelligence.

    Usage:
        mi = ModelIntelligence()
        result = mi.extract(
            title="MagSafe Case Compatible with iPhone 15 Pro Max",
            product_type="phone_case",
            brand="Apple",
        )
        # result.model = None (it's a case, not an iPhone)
        # result.compatible_models = ["iPhone 15 Pro Max"]
        # result.is_accessory = True
    """

    def extract(
        self,
        title: str,
        product_type: Optional[str] = None,
        brand: Optional[str] = None,
    ) -> ModelIntelligenceResult:
        """
        Extract model intelligence from a product title.

        Args:
            title: Raw product title
            product_type: Detected product type from QueryParser
            brand: Detected brand from QueryParser

        Returns:
            ModelIntelligenceResult with model, variant, generation,
            compatible_models, and confidence.
        """
        if not title or not title.strip():
            return ModelIntelligenceResult()

        title_clean = title.strip()

        # Step 1: Determine if this is an accessory
        is_accessory = self._is_accessory(title_clean, product_type)

        # Step 2: Extract all model candidates from title
        model_candidates = self._extract_model_candidates(title_clean)

        # Step 3: Separate product model from compatible models
        if is_accessory:
            compatible_models = [m[0] for m in model_candidates]
            product_model = None
            model_family = None
        else:
            compatible_models = []
            if model_candidates:
                # Use the most specific (longest) match
                best = max(model_candidates, key=lambda m: len(m[0]))
                product_model = best[0]
                model_family = best[1]
            else:
                product_model = None
                model_family = None

        # Step 4: Extract generation
        generation = self._extract_generation(title_clean)

        # Step 5: Extract variant
        variant = self._extract_variant(title_clean, product_model, generation)

        # Step 6: Calculate confidence
        confidence = self._calculate_confidence(
            product_model, model_family, generation, variant,
            is_accessory, compatible_models, brand,
        )

        return ModelIntelligenceResult(
            model=product_model,
            model_family=model_family,
            generation=generation,
            variant=variant,
            compatible_models=compatible_models,
            is_accessory=is_accessory,
            confidence=confidence,
        )

    def _is_accessory(
        self,
        title: str,
        product_type: Optional[str],
    ) -> bool:
        """
        Determine if the product is an accessory for another device.

        Uses two signals:
        1. Product type is a known accessory type
        2. Title contains accessory context phrases ("case for", "compatible with")
        """
        # Signal 1: Product type
        if product_type and product_type in ACCESSORY_PRODUCT_TYPES:
            return True

        # Signal 2: Title context phrases
        title_lower = title.lower()
        for pattern in ACCESSORY_FOR_PATTERNS:
            if pattern.search(title_lower):
                return True

        return False

    def _extract_model_candidates(
        self,
        title: str,
    ) -> List[Tuple[str, str]]:
        """
        Extract all model candidates from title.

        Returns list of (model_string, model_family) tuples.
        Filters out false positives.
        """
        candidates = []
        seen = set()

        for pattern, family, brand_hint in MODEL_PATTERNS:
            for match in pattern.finditer(title):
                model_str = match.group(1).strip()
                model_key = model_str.lower()

                # Skip duplicates
                if model_key in seen:
                    continue

                # Skip false positives
                if self._is_false_positive(model_str, title):
                    continue

                seen.add(model_key)
                candidates.append((model_str, family))

        return candidates

    def _is_false_positive(self, model_str: str, full_title: str) -> bool:
        """
        Check if a model candidate is actually a false positive.

        Prevents "2 pack", "6ft", "5 buttons", "100W" from being models.
        """
        model_lower = model_str.lower().strip()

        # Single digit
        if SINGLE_DIGIT.match(model_lower):
            return True

        # Standalone year
        if YEAR_PATTERN.fullmatch(model_lower):
            return True

        # Check if the model string appears in a false-positive context
        # in the full title
        if FALSE_POSITIVE_CONTEXTS.search(full_title):
            # The title has false-positive patterns, but is THIS specific
            # match a false positive? Check if the model string overlaps
            # with the false-positive context.
            fp_match = FALSE_POSITIVE_CONTEXTS.search(full_title)
            if fp_match and model_lower in fp_match.group(0).lower():
                return True

        return False

    def _extract_generation(self, title: str) -> Optional[str]:
        """
        Extract generation indicator from title.

        Examples: "2nd Gen", "Gen 3", "V2", "Mk II", "Series 9"
        """
        for pattern in GENERATION_PATTERNS:
            match = pattern.search(title)
            if match:
                return match.group(0).strip()
        return None

    def _extract_variant(
        self,
        title: str,
        model: Optional[str],
        generation: Optional[str],
    ) -> Optional[str]:
        """
        Extract variant information not captured by model or generation.

        Variants include: USB-C, Lightning, GPS + Cellular, etc.

        Does NOT include storage/memory (those are attributes).
        Does NOT include generation (already extracted separately).
        Does NOT include color (that is an attribute).
        """
        title_lower = title.lower()
        variant_parts = []

        # Remove model and generation from title to avoid re-extraction
        cleaned = title_lower
        if model:
            cleaned = cleaned.replace(model.lower(), " ")
        if generation:
            cleaned = cleaned.replace(generation.lower(), " ")

        # Check for connectivity variants
        for conn in sorted(VARIANT_CONNECTIVITY, key=len, reverse=True):
            pattern = r"(?<!\w)" + re.escape(conn) + r"(?!\w)"
            if re.search(pattern, cleaned):
                variant_parts.append(conn.upper())
                # Remove to prevent double-matching
                cleaned = re.sub(pattern, " ", cleaned)

        # Check for edition markers
        edition_patterns = [
            r"\b(International\s+Version)\b",
            r"\b(Global\s+Version)\b",
            r"\b(US\s+Version)\b",
            r"\b(UK\s+Version)\b",
            r"\b(Japanese?\s+Version)\b",
        ]
        for pat in edition_patterns:
            match = re.search(pat, cleaned, re.IGNORECASE)
            if match:
                variant_parts.append(match.group(1).strip())

        if not variant_parts:
            return None

        return " ".join(variant_parts)

    def _calculate_confidence(
        self,
        model: Optional[str],
        model_family: Optional[str],
        generation: Optional[str],
        variant: Optional[str],
        is_accessory: bool,
        compatible_models: List[str],
        brand: Optional[str],
    ) -> float:
        """
        Calculate confidence in model extraction (0.0-1.0).

        This is about extraction quality, not match quality.
        """
        score = 0.0

        if is_accessory:
            # For accessories, confidence is about compatible model detection
            if compatible_models:
                score = 0.70
                if brand:
                    score += 0.10
            else:
                score = 0.30  # Accessory but no compatible model found
        else:
            # For devices, confidence is about model detection
            if model:
                score = 0.50
                if model_family:
                    score += 0.10
                if brand:
                    score += 0.10
                if generation:
                    score += 0.10
                if variant:
                    score += 0.05
            else:
                score = 0.15  # No model detected

        return min(1.0, round(score, 3))