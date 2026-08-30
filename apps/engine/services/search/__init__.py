"""
REHU Search Intelligence Module.

Provides query understanding, relevance scoring, product deduplication,
and price analysis — all rule-based, no AI/ML APIs.

Usage:
    from services.search import QueryParser, RelevanceScorer, ProductDeduplicator

    # Parse user intent
    intent = QueryParser().parse("Apple AirPods Pro 2")

    # Score listing relevance
    relevance = RelevanceScorer().score(intent, listing)

    # Deduplicate products
    groups = ProductDeduplicator().deduplicate(ranked_products)
"""
from .query_parser import QueryParser, SearchIntent
from .relevance import RelevanceScorer
from .deduplication import ProductDeduplicator
from .price_analysis import PriceAnalyzer, PriceStats

__all__ = [
    "QueryParser",
    "SearchIntent",
    "RelevanceScorer",
    "ProductDeduplicator",
    "PriceAnalyzer",
    "PriceStats",
]