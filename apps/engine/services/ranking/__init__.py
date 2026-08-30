"""
Product ranking service.

Ranks eBay search results by observed demand and market signals,
reusing existing Phase 3 market analysis rather than duplicating it.

Does NOT rank by price alone.
Does NOT invent sales figures.
Does NOT make additional eBay API calls.

Usage:
    from services.ranking import ProductRankingService

    ranker = ProductRankingService()
    ranked = ranker.rank(
        listings=results["items"],
        total_available=results["total"],
    )

    for r in ranked:
        print(f"{r.rank}. {r.demand_label} — {r.title[:50]}")
"""
from .ranker import ProductRankingService, RankedProduct, DemandLabel

__all__ = [
    "ProductRankingService",
    "RankedProduct",
    "DemandLabel",
]