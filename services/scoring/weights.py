"""
Scoring weight configuration loader.

Loads weights from config/scoring_weights.yaml with Pydantic validation.
Falls back to config/settings.py if YAML is unavailable.
"""
from pathlib import Path
from typing import Dict, Optional

import yaml
from pydantic import BaseModel, model_validator

from utils.logger import get_logger

logger = get_logger(__name__)

# Default path relative to project root
_DEFAULT_YAML_PATH = Path("config/scoring_weights.yaml")


class ScoringWeights(BaseModel):
    """
    Top-level opportunity scoring weights.

    All five weights must sum to 1.0 (±0.02 tolerance for float rounding).
    """

    market_signals: float
    competition_signals: float
    economics_signals: float
    supplier_match_signals: float
    confidence_bonus: float

    @model_validator(mode="after")
    def validate_sum(self) -> "ScoringWeights":
        total = (
            self.market_signals
            + self.competition_signals
            + self.economics_signals
            + self.supplier_match_signals
            + self.confidence_bonus
        )
        if abs(total - 1.0) > 0.02:
            raise ValueError(
                f"Scoring weights must sum to 1.0 (±0.02), got {total:.4f}. "
                f"Weights: market={self.market_signals}, "
                f"competition={self.competition_signals}, "
                f"economics={self.economics_signals}, "
                f"match={self.supplier_match_signals}, "
                f"confidence={self.confidence_bonus}"
            )
        return self

    def to_dict(self) -> Dict[str, float]:
        return {
            "market_signals": self.market_signals,
            "competition_signals": self.competition_signals,
            "economics_signals": self.economics_signals,
            "supplier_match_signals": self.supplier_match_signals,
            "confidence_bonus": self.confidence_bonus,
        }


class EconomicsSubWeights(BaseModel):
    """Sub-weights for the economics/profit dimension."""

    profit_margin: float = 0.40
    absolute_profit: float = 0.35
    roi: float = 0.25

    @model_validator(mode="after")
    def validate_sum(self) -> "EconomicsSubWeights":
        total = self.profit_margin + self.absolute_profit + self.roi
        if abs(total - 1.0) > 0.02:
            raise ValueError(
                f"Economics sub-weights must sum to 1.0, got {total:.4f}"
            )
        return self


class MatchSubWeights(BaseModel):
    """Sub-weights for the supplier match quality dimension."""

    match_confidence: float = 0.50
    supplier_rating: float = 0.30
    attribute_similarity: float = 0.20

    @model_validator(mode="after")
    def validate_sum(self) -> "MatchSubWeights":
        total = self.match_confidence + self.supplier_rating + self.attribute_similarity
        if abs(total - 1.0) > 0.02:
            raise ValueError(
                f"Match sub-weights must sum to 1.0, got {total:.4f}"
            )
        return self


class ScoringThresholds(BaseModel):
    """Score thresholds for recommendation classification."""

    excellent_score: float = 80.0
    good_score: float = 65.0
    moderate_score: float = 50.0
    poor_score: float = 35.0

    high_confidence: float = 0.80
    medium_confidence: float = 0.60
    low_confidence: float = 0.40


class ScoringConfig(BaseModel):
    """Complete scoring configuration bundle."""

    weights: ScoringWeights
    thresholds: ScoringThresholds
    economics_sub: EconomicsSubWeights
    match_sub: MatchSubWeights
    source: str  # "yaml" or "settings"


def load_scoring_config(
    yaml_path: Optional[Path] = None,
) -> ScoringConfig:
    """
    Load complete scoring configuration.

    Priority:
    1. YAML file (config/scoring_weights.yaml) — richest source
    2. Pydantic settings (config/settings.py) — fallback for top-level weights
    """
    path = yaml_path or _DEFAULT_YAML_PATH

    if path.exists():
        try:
            return _load_from_yaml(path)
        except Exception as e:
            logger.warning(
                f"Failed to load scoring weights from {path}: {e}. "
                f"Falling back to settings."
            )

    return _load_from_settings()


def _load_from_yaml(path: Path) -> ScoringConfig:
    """Load and validate scoring config from YAML file."""
    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping, got {type(data).__name__}")

    # Top-level weights
    weights_data = data.get("opportunity_score", {})
    weights = ScoringWeights(
        market_signals=weights_data.get("market_signals", 0.30),
        competition_signals=weights_data.get("competition_signals", 0.20),
        economics_signals=weights_data.get("economics_signals", 0.30),
        supplier_match_signals=weights_data.get("supplier_match_signals", 0.15),
        confidence_bonus=weights_data.get("confidence_bonus", 0.05),
    )

    # Thresholds
    thresholds_data = data.get("thresholds", {})
    thresholds = ScoringThresholds(
        excellent_score=thresholds_data.get("excellent_score", 80),
        good_score=thresholds_data.get("good_score", 65),
        moderate_score=thresholds_data.get("moderate_score", 50),
        poor_score=thresholds_data.get("poor_score", 35),
        high_confidence=thresholds_data.get("high_confidence", 0.80),
        medium_confidence=thresholds_data.get("medium_confidence", 0.60),
        low_confidence=thresholds_data.get("low_confidence", 0.40),
    )

    # Economics sub-weights
    econ_data = data.get("economics_signals", {})
    economics_sub = EconomicsSubWeights(
        profit_margin=econ_data.get("profit_margin", 0.40),
        absolute_profit=econ_data.get("absolute_profit", 0.35),
        roi=econ_data.get("roi", 0.25),
    )

    # Match sub-weights (supports optional supplier_rating)
    match_data = data.get("supplier_match_signals", {})
    match_sub = MatchSubWeights(
        match_confidence=match_data.get("match_confidence", 0.50),
        supplier_rating=match_data.get("supplier_rating", 0.0),
        attribute_similarity=match_data.get("attribute_similarity", 0.20),
    )

    logger.info(f"Loaded scoring weights from {path}")

    return ScoringConfig(
        weights=weights,
        thresholds=thresholds,
        economics_sub=economics_sub,
        match_sub=match_sub,
        source="yaml",
    )


def _load_from_settings() -> ScoringConfig:
    """Load top-level weights from Pydantic settings with default sub-weights."""
    from config import settings

    sw = settings.scoring_weights

    weights = ScoringWeights(
        market_signals=sw.get("market_signals", 0.30),
        competition_signals=sw.get("competition_signals", 0.20),
        economics_signals=sw.get("economics_signals", 0.30),
        supplier_match_signals=sw.get("supplier_match_signals", 0.15),
        confidence_bonus=sw.get("confidence_bonus", 0.05),
    )

    logger.info("Loaded scoring weights from settings (YAML unavailable)")

    return ScoringConfig(
        weights=weights,
        thresholds=ScoringThresholds(),
        economics_sub=EconomicsSubWeights(),
        match_sub=MatchSubWeights(),
        source="settings",
    )