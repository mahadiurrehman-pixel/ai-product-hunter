"""
Opportunity Analysis Pipeline Orchestrator.

Provides an end-to-end workflow chaining:
1. Runtime Marketplace Validation
2. eBay Browse API Search (Cache-first with retries)
3. Market & Competition Signal Analysis
4. Policy Risk Assessment
5. AliExpress Supplier Discovery (Mock / Real)
6. Pairwise Product Matching (Phase 5 Matcher)
7. Multi-Jurisdiction Profit & Fee Calculation (Phase 6 Calculator)
8. Unified Opportunity Scoring (Phase 7 Scorer)
9. Database Persistence (Listings, Matches, Scores)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from sqlalchemy.orm import Session

from services.aliexpress import get_adapter
from services.aliexpress.base_adapter import BaseAliExpressAdapter
from services.aliexpress.repository import AliExpressRepository
from services.ebay.cache import EbayCacheService
from services.ebay.client import EbayClient
from services.marketplace import (
    Marketplace,
    to_ebay_marketplace,
    validate_marketplace,
)
from services.matching.matcher import ProductMatcher, ProductMatchResult
from services.matching.repository import MatchRepository
from services.policy.checker import PolicyChecker
from services.policy.models import PolicyAssessment
from services.profit.calculator import ProfitCalculator
from services.profit.models import ProfitResult
from services.scoring.adapter import MatchToProfitAdapter
from services.scoring.competition_signals import (
    CompetitionSignals,
    CompetitionSignalsAnalyzer,
)
from services.scoring.market_signals import (
    MarketSignals,
    MarketSignalsAnalyzer,
)
from services.scoring.repository import OpportunityScoreRepository
from services.scoring.unified_scorer import (
    UnifiedOpportunityScore,
    UnifiedOpportunityScorer,
)
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MatchOpportunity:
    """Complete evaluation for a single eBay-supplier pair."""

    match_result: ProductMatchResult
    profit_result: ProfitResult
    opportunity_score: UnifiedOpportunityScore
    product_match_db_id: Optional[int] = None
    opportunity_score_db_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "match": self.match_result.to_dict(),
            "profit": self.profit_result.to_dict(),
            "score": self.opportunity_score.to_dict(),
            "db_ids": {
                "product_match_id": self.product_match_db_id,
                "opportunity_score_id": self.opportunity_score_db_id,
            },
        }


@dataclass
class PipelineResult:
    """Full end-to-end research result for an eBay listing."""

    ebay_listing: Dict[str, Any]
    policy_assessment: PolicyAssessment
    matches: List[MatchOpportunity] = field(default_factory=list)
    market_signals: Optional[MarketSignals] = None
    competition_signals: Optional[CompetitionSignals] = None
    best_opportunity: Optional[MatchOpportunity] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ebay_listing": self.ebay_listing,
            "policy": self.policy_assessment.to_dict(),
            "market_signals": (
                self.market_signals.overall_market_score
                if self.market_signals
                else None
            ),
            "competition_signals": (
                self.competition_signals.overall_competition_score
                if self.competition_signals
                else None
            ),
            "matches_count": len(self.matches),
            "matches": [m.to_dict() for m in self.matches],
            "best_opportunity": (
                self.best_opportunity.to_dict()
                if self.best_opportunity
                else None
            ),
        }


class OpportunityPipeline:
    """
    End-to-end Opportunity Research Pipeline.

    Orchestrates ingestion, matching, economics, and scoring across
    runtime-selected marketplaces.
    """

    def __init__(
        self,
        ebay_cache_service: Optional[EbayCacheService] = None,
        ali_adapter: Optional[BaseAliExpressAdapter] = None,
        matcher: Optional[ProductMatcher] = None,
        profit_calculator: Optional[ProfitCalculator] = None,
        policy_checker: Optional[PolicyChecker] = None,
        scorer: Optional[UnifiedOpportunityScorer] = None,
    ):
        self._cache_service = ebay_cache_service
        self._ali_adapter = ali_adapter or get_adapter()
        self._matcher = matcher or ProductMatcher()
        self._profit_calc = profit_calculator or ProfitCalculator()
        self._policy_checker = policy_checker or PolicyChecker()
        self._scorer = scorer or UnifiedOpportunityScorer()
        self._adapter = MatchToProfitAdapter()
        self._market_analyzer = MarketSignalsAnalyzer()
        self._competition_analyzer = CompetitionSignalsAnalyzer()

    def analyze(
        self,
        query: str,
        marketplace: Union[str, Marketplace] = Marketplace.US,
        limit: int = 20,
        supplier_limit: int = 5,
        min_match_score: float = 0.60,
        profit_defaults: Optional[Dict[str, Any]] = None,
        db: Optional[Session] = None,
    ) -> List[PipelineResult]:
        """
        Execute full opportunity research workflow for a search query.

        Args:
            query: Target search keywords (e.g. "wireless earbuds")
            marketplace: Runtime target marketplace ("US", "UK", "DE", "AU", "CA" or Marketplace enum)
            limit: Maximum eBay listings to retrieve and evaluate
            supplier_limit: Maximum supplier candidates to compare per listing
            min_match_score: Minimum match quality threshold (default: 0.60)
            profit_defaults: Optional dictionary of profit calculator overrides
            db: Optional SQLAlchemy Session for persisting listings, matches, and scores

        Returns:
            List of PipelineResult objects containing opportunities sorted by score
        """
        canon_mp = validate_marketplace(marketplace)
        profit_opts = profit_defaults or {}

        # 1. Initialize marketplace-aware eBay cache service
        cache_svc = self._get_cache_service(canon_mp)

        # 2. Ingest eBay listings with caching & database persistence
        logger.info(
            f"Pipeline searching eBay: query='{query}', marketplace={canon_mp.value}, limit={limit}"
        )
        search_res = cache_svc.search_items(
            query=query, limit=limit, db=db
        )
        items = search_res.get("items", [])
        total_available = search_res.get("total")

        if not items:
            logger.warning(f"No eBay items found for query='{query}' on {canon_mp.value}")
            return []

        # 3. Analyze batch Market and Competition signals
        market_signals = self._market_analyzer.analyze(
            items, total_available=total_available
        )
        competition_signals = self._competition_analyzer.analyze(items)

        results: List[PipelineResult] = []

        # 4. Process each listing
        for listing in items:
            # 4a. Policy Assessment
            policy_assessment = self._policy_checker.check(
                listing, marketplace=to_ebay_marketplace(canon_mp).value
            )
            
            # 4b. Find potential AliExpress suppliers
            listing_title = listing.get("title", "")
            suppliers = self._ali_adapter.search_products(
                listing_title, limit=supplier_limit
            )

            # Persist AliExpress listings if db session provided
            if db and suppliers:
                try:
                    AliExpressRepository.save_products_bulk(db, suppliers)
                except Exception as e:
                    logger.warning(f"Failed to persist supplier listings: {e}")

            # 4c. Match eBay product against AliExpress candidates
            match_results = self._matcher.find_matches(
                ebay_listing=listing,
                aliexpress_products=suppliers,
                min_score=min_match_score,
            )

            # Diagnostic: track why matches may be empty
            listing_diagnostics = {
                "ebay_title": listing.get("title", ""),
                "supplier_candidates_found": len(suppliers),
                "matches_above_threshold": len(match_results),
                "min_match_score": min_match_score,
                "match_attempted": len(suppliers) > 0,
            }

            evaluated_matches: List[MatchOpportunity] = []

            # 4d. Process each match
            for match_res in match_results:
                match_id = None
                # Persist match record if db provided
                if db:
                    try:
                        match_rec = MatchRepository.save_match(db, match_res)
                        if match_rec:
                            match_id = match_rec.id
                    except Exception as e:
                        logger.warning(f"Failed to persist match record: {e}")

                # 4e. Adapt to ProfitInput & Calculate Profit
                profit_input = self._adapter.convert(
                    match_result=match_res,
                    marketplace=canon_mp,
                    ebay_listing=listing,
                    **profit_opts,
                )
                profit_result = self._profit_calc.calculate(profit_input)

                # 4f. Calculate Unified Opportunity Score
                opp_score = self._scorer.score(
                    market_signals=market_signals,
                    competition_signals=competition_signals,
                    profit_result=profit_result,
                    match_result=match_res,
                    policy_assessment=policy_assessment,
                )

                # 4g. Persist Opportunity Score if db and match_id exist
                score_id = None
                if db and match_id:
                    try:
                        score_rec = OpportunityScoreRepository.save_score(
                            db=db, score=opp_score, product_match_id=match_id
                        )
                        if score_rec:
                            score_id = score_rec.id
                    except Exception as e:
                        logger.warning(f"Failed to persist score record: {e}")

                evaluated_matches.append(
                    MatchOpportunity(
                        match_result=match_res,
                        profit_result=profit_result,
                        opportunity_score=opp_score,
                        product_match_db_id=match_id,
                        opportunity_score_db_id=score_id,
                    )
                )

            # Sort matches by opportunity score descending
            evaluated_matches.sort(
                key=lambda m: m.opportunity_score.final_score, reverse=True
            )
            best_opp = evaluated_matches[0] if evaluated_matches else None

            results.append(
                PipelineResult(
                    ebay_listing=listing,
                    policy_assessment=policy_assessment,
                    matches=evaluated_matches,
                    market_signals=market_signals,
                    competition_signals=competition_signals,
                    best_opportunity=best_opp,
                    diagnostics=listing_diagnostics,
                )
            )
        # Sort overall results by highest opportunity score
        results.sort(
            key=lambda r: (
                r.best_opportunity.opportunity_score.final_score
                if r.best_opportunity
                else -1.0
            ),
            reverse=True,
        )

        return results

    def _get_cache_service(self, marketplace: Marketplace) -> EbayCacheService:
        """Get or initialize marketplace-aware EbayCacheService."""
        if self._cache_service:
            return self._cache_service

        ebay_client = EbayClient(
            marketplace=to_ebay_marketplace(marketplace)
        )
        return EbayCacheService(ebay_client=ebay_client)