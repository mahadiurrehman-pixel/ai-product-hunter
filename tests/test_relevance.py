"""Tests for RelevanceScorer."""
import pytest

from services.search.query_parser import QueryParser
from services.search.relevance import RelevanceScorer


class TestRelevanceScorer:
    @pytest.fixture
    def scorer(self):
        return RelevanceScorer()

    @pytest.fixture
    def parser(self):
        return QueryParser()

    def test_high_relevance_exact_match(self, scorer, parser):
        intent = parser.parse("wireless bluetooth earbuds")
        listing = {
            "title": "Wireless Bluetooth Earbuds TWS Noise Cancelling",
        }
        score = scorer.score(intent, listing)
        assert score >= 60

    def test_low_relevance_wrong_product(self, scorer, parser):
        intent = parser.parse("wireless earbuds")
        listing = {
            "title": "Mechanical Gaming Keyboard RGB Backlit",
        }
        score = scorer.score(intent, listing)
        assert score < 40

    def test_medium_relevance_related_product(self, scorer, parser):
        intent = parser.parse("wireless earbuds")
        listing = {
            "title": "Bluetooth Speaker Portable Waterproof",
        }
        score = scorer.score(intent, listing)
        # Speaker is audio but not earbuds
        assert 20 < score < 70

    def test_brand_match_boosts_relevance(self, scorer, parser):
        intent = parser.parse("Apple AirPods")
        listing_match = {
            "title": "Apple AirPods Pro 2nd Generation",
        }
        listing_no_match = {
            "title": "Samsung Galaxy Buds Pro",
        }
        score_match = scorer.score(intent, listing_match)
        score_no = scorer.score(intent, listing_no_match)
        assert score_match > score_no

    def test_case_vs_earbuds(self, scorer, parser):
        """Searching for earbuds should rank earbuds higher than cases."""
        intent = parser.parse("wireless earbuds")
        listing_earbuds = {
            "title": "Wireless Bluetooth Earbuds TWS",
        }
        listing_case = {
            "title": "Earbuds Carrying Case Storage Bag",
        }
        score_earbuds = scorer.score(intent, listing_earbuds)
        score_case = scorer.score(intent, listing_case)
        assert score_earbuds > score_case

    def test_empty_intent_returns_zero(self, scorer):
        from services.search.query_parser import SearchIntent
        intent = SearchIntent(raw_query="", normalized_query="")
        listing = {"title": "Some Product"}
        score = scorer.score(intent, listing)
        assert score == 0.0

    def test_empty_listing_returns_zero(self, scorer, parser):
        intent = parser.parse("earbuds")
        score = scorer.score(intent, {})
        assert score == 0.0

    def test_score_always_0_to_100(self, scorer, parser):
        queries = [
            "wireless earbuds",
            "Apple iPhone 15 Pro Max 256GB",
            "used laptop cheap",
            "bluetooth keyboard",
        ]
        listing = {
            "title": "Wireless Bluetooth Earbuds TWS Noise Cancelling",
        }
        for q in queries:
            intent = parser.parse(q)
            score = scorer.score(intent, listing)
            assert 0 <= score <= 100, f"Score {score} out of range for '{q}'"