"""
Bundle / Multipack Detection (Pre-Phase 6.4).

Detects quantity, pack size, bundles, kits, combos, and multi-item
listings from product titles.

Rules:
- Quantity mismatch → explicit evidence
- Bundle vs single → explicit evidence
- Unknown quantity → neutral
- Unknown bundle status → neutral
- Do not hard-reject merely because quantity is unavailable
"""
import re
from dataclasses import dataclass
from typing import Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BundleInfo:
    """Detected bundle/quantity information from a product title."""

    quantity: int = 1
    is_bundle: bool = False
    is_kit: bool = False
    is_combo: bool = False
    is_multipack: bool = False
    raw_match: str = ""
    confidence: str = "unknown"  # high, medium, unknown

    def to_dict(self) -> dict:
        return {
            "quantity": self.quantity,
            "is_bundle": self.is_bundle,
            "is_kit": self.is_kit,
            "is_combo": self.is_combo,
            "is_multipack": self.is_multipack,
            "raw_match": self.raw_match,
            "confidence": self.confidence,
        }


class BundleDetector:
    """
    Detects bundle/multipack/quantity information from product titles.

    Patterns detected:
    - "2 Pack", "3 Pack", "Pack of 2", "Pack of 3"
    - "Set of 2", "Set of 3"
    - "Bundle", "Kit", "Combo"
    - "Complete Set"
    - "x2", "x3", "×2", "×3"
    - "2-Pack", "3-Pack"
    """

    # Pack patterns: "2 pack", "2-pack", "pack of 2"
    PACK_PATTERNS = [
        re.compile(
            r"\b(\d+)\s*[-]?\s*pack\b", re.IGNORECASE
        ),
        re.compile(
            r"\bpack\s+of\s+(\d+)\b", re.IGNORECASE
        ),
        re.compile(
            r"\b(\d+)\s*[-]?\s*pcs?\b", re.IGNORECASE
        ),
        re.compile(
            r"\b(\d+)\s*[-]?\s*pieces?\b", re.IGNORECASE
        ),
        re.compile(
            r"\bset\s+of\s+(\d+)\b", re.IGNORECASE
        ),
        re.compile(
            r"\b(\d+)\s*[-]?\s*set\b", re.IGNORECASE
        ),
        re.compile(
            r"\bx(\d+)\b", re.IGNORECASE
        ),
        re.compile(
            r"\b×(\d+)\b", re.IGNORECASE
        ),
    ]

    # Bundle/kit/combo keywords
    BUNDLE_KEYWORDS = re.compile(
        r"\b(bundle|complete\s+set|combo|kit)\b",
        re.IGNORECASE,
    )

    def detect(self, title: str) -> BundleInfo:
        """
        Detect bundle/multipack/quantity from a product title.

        Args:
            title: Product title string

        Returns:
            BundleInfo with detected quantity and bundle status
        """
        if not title or not title.strip():
            return BundleInfo()

        quantity = 1
        raw_match = ""
        confidence = "unknown"

        # Check pack patterns
        for pattern in self.PACK_PATTERNS:
            match = pattern.search(title)
            if match:
                try:
                    qty = int(match.group(1))
                    if 2 <= qty <= 100:  # Sanity check
                        quantity = qty
                        raw_match = match.group(0)
                        confidence = "high"
                        break
                except (ValueError, IndexError):
                    continue

        # Check bundle/kit/combo keywords
        bundle_match = self.BUNDLE_KEYWORDS.search(title)
        is_bundle = False
        is_kit = False
        is_combo = False
        is_multipack = quantity > 1

        if bundle_match:
            keyword = bundle_match.group(1).lower()
            raw_match = raw_match or bundle_match.group(0)
            if keyword == "bundle":
                is_bundle = True
                confidence = "high" if confidence == "unknown" else confidence
            elif keyword == "kit":
                is_kit = True
                confidence = "high" if confidence == "unknown" else confidence
            elif keyword == "combo":
                is_combo = True
                confidence = "high" if confidence == "unknown" else confidence
            elif keyword == "complete set":
                is_bundle = True
                confidence = "high" if confidence == "unknown" else confidence

        return BundleInfo(
            quantity=quantity,
            is_bundle=is_bundle,
            is_kit=is_kit,
            is_combo=is_combo,
            is_multipack=is_multipack,
            raw_match=raw_match,
            confidence=confidence,
        )

    def compare(
        self,
        title_a: str,
        title_b: str,
    ) -> Tuple[float, str]:
        """
        Compare bundle/quantity between two product titles.

        Returns:
            Tuple of (similarity 0.0-1.0, explanation)
        """
        info_a = self.detect(title_a)
        info_b = self.detect(title_b)

        # Both unknown quantity — neutral
        if info_a.confidence == "unknown" and info_b.confidence == "unknown":
            return 0.5, "Quantity unknown for both products"

        # One unknown — neutral
        if info_a.confidence == "unknown" or info_b.confidence == "unknown":
            return 0.5, "Quantity unknown for one product"

        # Both known — compare
        if info_a.quantity == info_b.quantity:
            if info_a.is_bundle == info_b.is_bundle:
                return 1.0, f"Same quantity ({info_a.quantity})"
            else:
                return 0.6, (
                    f"Same quantity ({info_a.quantity}) but "
                    f"bundle status differs"
                )

        # Different quantities
        return 0.2, (
            f"Quantity mismatch: {info_a.quantity} vs {info_b.quantity}"
        )