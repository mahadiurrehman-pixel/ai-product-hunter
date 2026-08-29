"""
Tests for Opportunity Analysis Pipeline Orchestrator (Phase 7 Step 7).
"""
import uuid
from decimal import Decimal
from unittest.mock import Mock
import pytest

from models.ebay import EbayListing
from models.score import OpportunityScoreRecord
from services.marketplace import Marketplace
from services.pipeline import (
    OpportunityPipeline,
    PipelineResult,
    MatchOpportunity,
)
from services.policy.models import PolicyRiskLevel
from services.scoring.recommendation import Recommendation


@pytest.fixture
def mock_cache_service():
    service = Mock()
    service.search_items.return_value = {
        "total": 50,
        "items": [
            {
                "item_id": "v1|pipe_test_1|0",
                "title": "Apple AirPods Pro 2 USB-C White",
                "price_value": Decimal("189.99"),
                "price_currency": "USD",
                "marketplace": "EBAY_US",
                "seller": {"username": "trusted_seller", "feedback_score": 99.5},
                "shipping": {"cost": Decimal("0.00"), "free_shipping": True},
                "buying_format": "FIXED_PRICE",
                "condition": "New",
            },
            {
                "item_id": "v1|pipe_test_2|0",
                "title": "Apple AirPods Pro 2nd Gen Earphones",
                "price_value": Decimal("179.99"),
                "price_currency": "USD",
                "marketplace": "EBAY_US",
                "seller": {"username": "seller_two", "feedback_score": 98.0},
                "shipping": {"cost": Decimal("0.00"), "free_shipping": True},
                "buying_format": "FIXED_PRICE",
                "condition": "New",
            },
        ],
    }
    return service


@pytest.fixture
def pipeline(mock_cache_service):
    return OpportunityPipeline(ebay_cache_service=mock_cache_service)


class TestOpportunityPipeline:
    def test_analyze_end_to_end(self, pipeline):
        results = pipeline.analyze(
            query="Apple AirPods Pro 2",
            marketplace=Marketplace.US,
            limit=2,
            min_match_score=0.50,
        )

        assert isinstance(results, list)
        assert len(results) == 2

        # Verify all listings were analyzed
        item_ids = {r.ebay_listing["item_id"] for r in results}
        assert item_ids == {"v1|pipe_test_1|0", "v1|pipe_test_2|0"}

        first_res = results[0]
        assert isinstance(first_res, PipelineResult)
        assert first_res.market_signals is not None
        assert first_res.competition_signals is not None
        assert first_res.policy_assessment is not None
        assert first_res.policy_assessment.overall_risk in (
            PolicyRiskLevel.LOW,
            PolicyRiskLevel.REVIEW_REQUIRED,
            PolicyRiskLevel.MEDIUM,
            PolicyRiskLevel.HIGH,
        )

        # Check matched opportunities
        assert len(first_res.matches) >= 1
        best = first_res.best_opportunity
        assert isinstance(best, MatchOpportunity)
        assert best.match_result.match_score >= 0.50
        assert best.profit_result.marketplace == "US"
        assert best.opportunity_score.final_score > 0
        assert isinstance(best.opportunity_score.recommendation, Recommendation)

    def test_analyze_with_database_persistence(self, db_session, mock_cache_service):
        """Verify pipeline correctly stores records in SQLite."""
        uid = uuid.uuid4().hex[:6]
        mock_cache_service.search_items.return_value = {
            "total": 10,
            "items": [
                {
                    "item_id": f"v1|db_pipe_{uid}|0",
                    "title": "Apple AirPods Pro 2 USB-C White",
                    "price_value": Decimal("189.99"),
                    "price_currency": "USD",
                    "marketplace": "EBAY_US",
                    "seller": {"username": "seller_db", "feedback_score": 99.0},
                    "shipping": {"cost": Decimal("0.00"), "free_shipping": True},
                    "buying_format": "FIXED_PRICE",
                    "condition": "New",
                    "raw_data": {"item_id": f"v1|db_pipe_{uid}|0"},
                }
            ],
        }
        # Pre-persist the eBay listing to satisfy foreign keys
        ebay_rec = EbayListing(
            item_id=f"v1|db_pipe_{uid}|0",
            title="Apple AirPods Pro 2 USB-C White",
            price_value=Decimal("189.99"),
            price_currency="USD",
            marketplace="EBAY_US",
            raw_data={"item_id": f"v1|db_pipe_{uid}|0"},
        )
        db_session.add(ebay_rec)
        db_session.commit()

        pipeline_db = OpportunityPipeline(ebay_cache_service=mock_cache_service)
        results = pipeline_db.analyze(
            query="Apple AirPods Pro",
            marketplace="US",
            limit=1,
            db=db_session,
        )

        assert len(results) == 1
        best = results[0].best_opportunity
        if best and best.product_match_db_id:
            assert best.product_match_db_id is not None
            assert best.opportunity_score_db_id is not None

            # Query database directly to confirm persistence
            saved_score = (
                db_session.query(OpportunityScoreRecord)
                .filter(OpportunityScoreRecord.id == best.opportunity_score_db_id)
                .first()
            )
            assert saved_score is not None
            assert float(saved_score.overall_score) == pytest.approx(
                best.opportunity_score.final_score, rel=1e-2
            )

    def test_analyze_empty_search_results(self, pipeline, mock_cache_service):
        mock_cache_service.search_items.return_value = {"total": 0, "items": []}
        results = pipeline.analyze("nonexistent query xyz")
        assert results == []

    def test_analyze_all_marketplaces_dispatch(self, mock_cache_service):
        """Confirm pipeline passes target marketplace to profit and policies."""
        mock_cache_service.search_items.return_value = {
            "total": 5,
            "items": [
                {
                    "item_id": "v1|uk_pipe|0",
                    "title": "Apple AirPods Pro 2 USB-C White",
                    "price_value": Decimal("150.00"),
                    "price_currency": "GBP",
                    "marketplace": "EBAY_GB",
                    "raw_data": {"item_id": "v1|uk_pipe|0"},
                }
            ],
        }
        pipeline = OpportunityPipeline(ebay_cache_service=mock_cache_service)
        results = pipeline.analyze(
            query="AirPods",
            marketplace=Marketplace.UK,
        )

        assert len(results) == 1
        best = results[0].best_opportunity
        if best:
            assert best.profit_result.marketplace == "UK"
            assert best.profit_result.currency == "GBP"

    def test_pipeline_result_to_dict(self, pipeline):
        results = pipeline.analyze("AirPods", limit=1)
        if results:
            d = results[0].to_dict()
            assert "ebay_listing" in d
            assert "policy" in d
            assert "matches" in d
            assert "best_opportunity" in d