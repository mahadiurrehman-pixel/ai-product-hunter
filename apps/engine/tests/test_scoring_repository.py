"""
Tests for OpportunityScoreRepository (Phase 7 Step 6).
"""
import uuid
from decimal import Decimal
import pytest

from models.aliexpress import AliExpressListing
from models.ebay import EbayListing
from models.match import ProductMatch
from models.score import OpportunityScoreRecord
from services.scoring.recommendation import Recommendation
from services.scoring.repository import OpportunityScoreRepository
from services.scoring.unified_scorer import UnifiedOpportunityScore


@pytest.fixture
def sample_match(db_session):
    """Fixture providing a saved ProductMatch record with unique foreign keys."""
    uid = uuid.uuid4().hex[:8]

    # 1. Create eBay listing
    ebay = EbayListing(
        item_id=f"ebay_repo_{uid}",
        title="Wireless Bluetooth Earbuds",
        price_value=Decimal("49.99"),
        price_currency="USD",
        marketplace="EBAY_US",
        raw_data={"item_id": f"ebay_repo_{uid}", "title": "Wireless Bluetooth Earbuds"},
    )
    db_session.add(ebay)

    # 2. Create AliExpress listing
    ali = AliExpressListing(
        product_id=f"ali_repo_{uid}",
        title="TWS Bluetooth Earphones",
        price_value=Decimal("12.00"),
        price_currency="USD",
        product_url=f"https://aliexpress.com/item/{uid}",
        source="mock",
        raw_data={"product_id": f"ali_repo_{uid}", "title": "TWS Bluetooth Earphones"},
    )
    db_session.add(ali)
    db_session.commit()

    # 3. Create ProductMatch
    match = ProductMatch(
        ebay_listing_id=ebay.id,
        aliexpress_listing_id=ali.id,
        match_score=Decimal("0.8800"),
        confidence=Decimal("0.8500"),
        match_type="very_similar",
    )
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)
    return match


@pytest.fixture
def sample_score():
    return UnifiedOpportunityScore(
        final_score=82.5,
        recommendation=Recommendation.STRONG_BUY,
        confidence="high",
        market_score=85.0,
        competition_score=75.0,
        economics_score=88.0,
        match_quality_score=82.0,
        confidence_bonus=85.0,
        raw_weighted_score=82.5,
        policy_penalty=1.0,
        policy_risk_level="low",
        weights_used={"market_signals": 0.30, "economics_signals": 0.30},
        reasoning=["Strong market demand", "High profit margin"],
        warnings=[],
        assumptions=["Standard US fee rates"],
        market_details={"listings_analyzed": 20},
        competition_details={"competition_level": "Low"},
        economics_details={"margin": 45.0, "roi": 180.0},
        match_details={"match_type": "very_similar"},
    )


class TestOpportunityScoreRepository:
    def test_save_new_score(self, db_session, sample_match, sample_score):
        record = OpportunityScoreRepository.save_score(
            db=db_session,
            score=sample_score,
            product_match_id=sample_match.id,
        )

        assert record is not None
        assert record.id is not None
        assert record.product_match_id == sample_match.id
        assert float(record.overall_score) == 82.5
        assert record.recommendation == "strong_buy"
        assert float(record.market_signals_score) == 85.0
        assert float(record.economics_signals_score) == 88.0
        assert record.reasoning == ["Strong market demand", "High profit margin"]
        assert record.weights_used == {"market_signals": 0.30, "economics_signals": 0.30}
        assert record.evidence["policy_penalty"] == 1.0

    def test_save_score_upsert_updates_existing(
        self, db_session, sample_match, sample_score
    ):
        # First save
        OpportunityScoreRepository.save_score(
            db=db_session,
            score=sample_score,
            product_match_id=sample_match.id,
        )

        # Modify score and re-save
        updated_score = UnifiedOpportunityScore(
            final_score=68.0,
            recommendation=Recommendation.BUY,
            confidence="medium",
            market_score=70.0,
            competition_score=65.0,
            economics_score=70.0,
            match_quality_score=68.0,
            confidence_bonus=65.0,
            raw_weighted_score=68.0,
            policy_penalty=1.0,
            policy_risk_level="low",
            weights_used={"market_signals": 0.30},
            reasoning=["Updated reasoning"],
        )

        record = OpportunityScoreRepository.save_score(
            db=db_session,
            score=updated_score,
            product_match_id=sample_match.id,
        )

        assert float(record.overall_score) == 68.0
        assert record.recommendation == "buy"
        assert record.reasoning == ["Updated reasoning"]

        # Confirm only 1 record exists
        count = (
            db_session.query(OpportunityScoreRecord)
            .filter(OpportunityScoreRecord.product_match_id == sample_match.id)
            .count()
        )
        assert count == 1

    def test_save_score_missing_match_returns_none(self, db_session, sample_score):
        non_existent_id = 999999
        record = OpportunityScoreRepository.save_score(
            db=db_session,
            score=sample_score,
            product_match_id=non_existent_id,
        )
        assert record is None

    def test_get_by_match_id(self, db_session, sample_match, sample_score):
        OpportunityScoreRepository.save_score(
            db=db_session,
            score=sample_score,
            product_match_id=sample_match.id,
        )

        retrieved = OpportunityScoreRepository.get_by_match_id(
            db=db_session,
            product_match_id=sample_match.id,
        )

        assert retrieved is not None
        assert retrieved.product_match_id == sample_match.id
        assert float(retrieved.overall_score) == 82.5

    def test_get_top_opportunities(self, db_session, sample_match, sample_score):
        OpportunityScoreRepository.save_score(
            db=db_session,
            score=sample_score,
            product_match_id=sample_match.id,
        )

        top = OpportunityScoreRepository.get_top_opportunities(
            db=db_session,
            limit=10,
            min_score=50.0,
        )

        assert len(top) >= 1
        assert float(top[0].overall_score) >= 50.0

    def test_record_to_dict(self, db_session, sample_match, sample_score):
        record = OpportunityScoreRepository.save_score(
            db=db_session,
            score=sample_score,
            product_match_id=sample_match.id,
        )

        d = record.to_dict()
        assert d["id"] == record.id
        assert d["product_match_id"] == sample_match.id
        assert d["overall_score"] == 82.5
        assert d["recommendation"] == "strong_buy"
        assert d["component_scores"]["market_signals"] == 85.0