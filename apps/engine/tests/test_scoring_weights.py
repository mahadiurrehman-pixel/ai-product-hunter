"""
Tests for scoring weight configuration loader (Phase 7 Step 1).
"""
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from services.scoring.weights import (
    ScoringWeights,
    ScoringThresholds,
    EconomicsSubWeights,
    MatchSubWeights,
    ScoringConfig,
    load_scoring_config,
)


# =============================================================================
# ScoringWeights Validation
# =============================================================================

class TestScoringWeights:
    def test_valid_weights_sum_to_one(self):
        w = ScoringWeights(
            market_signals=0.30,
            competition_signals=0.20,
            economics_signals=0.30,
            supplier_match_signals=0.15,
            confidence_bonus=0.05,
        )
        total = sum(w.to_dict().values())
        assert abs(total - 1.0) < 0.01

    def test_invalid_weights_rejected(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            ScoringWeights(
                market_signals=0.50,
                competition_signals=0.50,
                economics_signals=0.50,
                supplier_match_signals=0.50,
                confidence_bonus=0.50,
            )

    def test_slightly_off_weights_accepted(self):
        """Float rounding tolerance of ±0.02."""
        w = ScoringWeights(
            market_signals=0.30,
            competition_signals=0.20,
            economics_signals=0.30,
            supplier_match_signals=0.15,
            confidence_bonus=0.06,  # sum = 1.01
        )
        assert w.confidence_bonus == 0.06

    def test_to_dict(self):
        w = ScoringWeights(
            market_signals=0.30,
            competition_signals=0.20,
            economics_signals=0.30,
            supplier_match_signals=0.15,
            confidence_bonus=0.05,
        )
        d = w.to_dict()
        assert "market_signals" in d
        assert "economics_signals" in d
        assert len(d) == 5


# =============================================================================
# Sub-Weights Validation
# =============================================================================

class TestEconomicsSubWeights:
    def test_defaults_sum_to_one(self):
        sub = EconomicsSubWeights()
        total = sub.profit_margin + sub.absolute_profit + sub.roi
        assert abs(total - 1.0) < 0.01

    def test_custom_valid(self):
        sub = EconomicsSubWeights(
            profit_margin=0.50,
            absolute_profit=0.30,
            roi=0.20,
        )
        assert sub.profit_margin == 0.50

    def test_invalid_rejected(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            EconomicsSubWeights(
                profit_margin=0.50,
                absolute_profit=0.50,
                roi=0.50,
            )

class TestMatchSubWeights:
    def test_defaults_sum_to_one(self):
        sub = MatchSubWeights()
        total = (
            sub.match_confidence
            + sub.supplier_rating
            + sub.attribute_similarity
        )
        assert abs(total - 1.0) < 0.01

    def test_invalid_rejected(self):
        with pytest.raises(ValueError, match="must sum to 1.0"):
            MatchSubWeights(
                match_confidence=0.80,
                supplier_rating=0.40,
                attribute_similarity=0.80,
            )

# =============================================================================
# Thresholds
# =============================================================================

class TestScoringThresholds:
    def test_defaults(self):
        t = ScoringThresholds()
        assert t.excellent_score == 80.0
        assert t.good_score == 65.0
        assert t.moderate_score == 50.0
        assert t.poor_score == 35.0
        assert t.high_confidence == 0.80
        assert t.medium_confidence == 0.60
        assert t.low_confidence == 0.40

    def test_custom_thresholds(self):
        t = ScoringThresholds(excellent_score=90, good_score=75)
        assert t.excellent_score == 90.0
        assert t.good_score == 75.0


# =============================================================================
# YAML Loading
# =============================================================================

class TestLoadFromYAML:
    def test_load_actual_yaml(self):
        """Load the real config/scoring_weights.yaml."""
        config = load_scoring_config()
        assert config.source in ("yaml", "settings")
        assert config.weights.market_signals > 0
        assert config.weights.economics_signals > 0
        assert config.thresholds.excellent_score >= 70

    def test_load_from_custom_path(self, tmp_path):
        """Load from a custom YAML file."""
        yaml_content = {
            "opportunity_score": {
                "market_signals": 0.25,
                "competition_signals": 0.25,
                "economics_signals": 0.25,
                "supplier_match_signals": 0.15,
                "confidence_bonus": 0.10,
            },
            "thresholds": {
                "excellent_score": 85,
                "good_score": 70,
                "moderate_score": 55,
                "poor_score": 40,
            },
            "economics_signals": {
                "profit_margin": 0.50,
                "absolute_profit": 0.30,
                "roi": 0.20,
            },
            "supplier_match_signals": {
                "match_confidence": 0.70,
                "attribute_similarity": 0.30,
            },
        }
        yaml_file = tmp_path / "test_weights.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(yaml_content, f)

        config = load_scoring_config(yaml_path=yaml_file)
        assert config.source == "yaml"
        assert config.weights.market_signals == 0.25
        assert config.thresholds.excellent_score == 85
        assert config.economics_sub.profit_margin == 0.50
        assert config.match_sub.match_confidence == 0.70

    def test_missing_yaml_falls_back_to_settings(self, tmp_path):
        """Non-existent YAML path falls back to settings."""
        fake_path = tmp_path / "nonexistent.yaml"
        config = load_scoring_config(yaml_path=fake_path)
        assert config.source == "settings"
        assert config.weights.market_signals > 0

    def test_invalid_yaml_falls_back_to_settings(self, tmp_path):
        """Malformed YAML falls back to settings."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("not: valid: yaml: [[[")
        config = load_scoring_config(yaml_path=bad_file)
        assert config.source == "settings"

    def test_yaml_with_invalid_weights_falls_back(self, tmp_path):
        """YAML with weights not summing to 1.0 falls back."""
        yaml_content = {
            "opportunity_score": {
                "market_signals": 0.90,
                "competition_signals": 0.90,
                "economics_signals": 0.90,
                "supplier_match_signals": 0.90,
                "confidence_bonus": 0.90,
            },
        }
        yaml_file = tmp_path / "bad_weights.yaml"
        with open(yaml_file, "w") as f:
            yaml.dump(yaml_content, f)

        config = load_scoring_config(yaml_path=yaml_file)
        assert config.source == "settings"


# =============================================================================
# ScoringConfig Bundle
# =============================================================================

class TestScoringConfig:
    def test_config_has_all_components(self):
        config = load_scoring_config()
        assert isinstance(config.weights, ScoringWeights)
        assert isinstance(config.thresholds, ScoringThresholds)
        assert isinstance(config.economics_sub, EconomicsSubWeights)
        assert isinstance(config.match_sub, MatchSubWeights)
        assert config.source in ("yaml", "settings")

    def test_yaml_config_has_correct_structure(self):
        """Verify the actual YAML matches expected structure."""
        yaml_path = Path("config/scoring_weights.yaml")
        if not yaml_path.exists():
            pytest.skip("YAML file not found")

        config = load_scoring_config()
        assert config.source == "yaml"

        # Verify weights match YAML values
        assert abs(config.weights.market_signals - 0.30) < 0.01
        assert abs(config.weights.competition_signals - 0.20) < 0.01
        assert abs(config.weights.economics_signals - 0.30) < 0.01
        assert abs(config.weights.supplier_match_signals - 0.15) < 0.01
        assert abs(config.weights.confidence_bonus - 0.05) < 0.01