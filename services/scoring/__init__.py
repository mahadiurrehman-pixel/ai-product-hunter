"""Scoring services for market analysis and opportunity evaluation."""
from .normalizer import ProductNormalizer
from .market_signals import MarketSignalsAnalyzer, MarketSignals
from .competition_signals import CompetitionSignalsAnalyzer, CompetitionSignals
from .opportunity_scorer import OpportunityScorer, OpportunityScore
from .weights import (
    ScoringWeights,
    ScoringThresholds,
    ScoringConfig,
    EconomicsSubWeights,
    MatchSubWeights,
    load_scoring_config,
)
from .normalizers import (
    normalize_market_score,
    normalize_competition_score,
    normalize_margin,
    normalize_absolute_profit,
    normalize_roi,
    normalize_profit_score,
    normalize_match_score,
    calculate_policy_penalty,
)
from .recommendation import (
    Recommendation,
    classify_recommendation,
)
from .adapter import (
    MatchToProfitAdapter,
)
from .unified_scorer import (
    UnifiedOpportunityScorer,
    UnifiedOpportunityScore,
)
from .repository import (
    OpportunityScoreRepository,
)

__all__ = [
    "ProductNormalizer",
    "MarketSignalsAnalyzer",
    "MarketSignals",
    "CompetitionSignalsAnalyzer",
    "CompetitionSignals",
    "OpportunityScorer",
    "OpportunityScore",
    "ScoringWeights",
    "ScoringThresholds",
    "ScoringConfig",
    "EconomicsSubWeights",
    "MatchSubWeights",
    "load_scoring_config",
    "normalize_market_score",
    "normalize_competition_score",
    "normalize_margin",
    "normalize_absolute_profit",
    "normalize_roi",
    "normalize_profit_score",
    "normalize_match_score",
    "calculate_policy_penalty",
    "Recommendation",
    "classify_recommendation",
    "MatchToProfitAdapter",
    "UnifiedOpportunityScorer",
    "UnifiedOpportunityScore",
    "OpportunityScoreRepository",
]