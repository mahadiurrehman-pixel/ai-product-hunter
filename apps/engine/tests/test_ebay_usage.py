"""
Tests for eBay API usage monitoring.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, MagicMock

from services.ebay.usage import UsageTracker
from models.audit import APIRequestLog


class TestUsageTracker:
    def test_get_today_usage_empty(self, db_session):
        tracker = UsageTracker()
        stats = tracker.get_today_usage(db_session)
        assert stats["api_requests"] == 0
        assert stats["cache_hits"] == 0
        assert stats["cache_hit_rate"] == 0.0

    def test_get_today_usage_with_data(self, db_session):
        tracker = UsageTracker()

        # Add some log entries
        now = datetime.now(timezone.utc)
        for i in range(5):
            db_session.add(APIRequestLog(
                service="ebay",
                endpoint="/search",
                method="GET",
                status_code=200,
                was_cached=False,
                error_occurred=False,
                response_time_ms=100,
                created_at=now,
            ))
        for i in range(3):
            db_session.add(APIRequestLog(
                service="ebay",
                endpoint="cache",
                method="CACHE",
                was_cached=True,
                error_occurred=False,
                created_at=now,
            ))
        db_session.commit()

        stats = tracker.get_today_usage(db_session)
        assert stats["api_requests"] == 5
        assert stats["cache_hits"] == 3
        assert stats["successful_requests"] == 5
        assert stats["total_requests"] == 8

    def test_get_usage_by_endpoint(self, db_session):
        tracker = UsageTracker()
        now = datetime.now(timezone.utc)

        # Use unique endpoint names to avoid collision with other tests
        for _ in range(3):
            db_session.add(APIRequestLog(
                service="ebay",
                endpoint="/test_search_unique",
                method="GET",
                was_cached=False,
                error_occurred=False,
                created_at=now,
            ))
        db_session.add(APIRequestLog(
            service="ebay",
            endpoint="/test_item_unique",
            method="GET",
            was_cached=False,
            error_occurred=False,
            created_at=now,
        ))
        db_session.commit()

        usage = tracker.get_usage_by_endpoint(db_session)
        assert usage.get("/test_search_unique") == 3
        assert usage.get("/test_item_unique") == 1
    def test_log_cache_event(self, db_session):
        tracker = UsageTracker()
        tracker.log_cache_event(
            db_session,
            event_type="CACHE_HIT",
            endpoint="/search",
            cache_key="abc123",
        )

        logs = db_session.query(APIRequestLog).filter(
            APIRequestLog.cache_key == "abc123"
        ).all()
        assert len(logs) == 1
        assert logs[0].was_cached is True