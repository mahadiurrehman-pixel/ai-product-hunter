"""
eBay API usage monitoring and metrics.

Provides lightweight usage statistics by querying the existing
APIRequestLog table. Does NOT introduce external monitoring
infrastructure (no Prometheus, Grafana, etc.).

Usage:
    tracker = UsageTracker()
    stats = tracker.get_today_usage()
    print(f"Cache hit rate: {stats['cache_hit_rate']}%")
"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.audit import APIRequestLog
from utils.logger import get_logger

logger = get_logger(__name__)


class UsageTracker:
    """
    Lightweight API usage tracker.

    Queries the existing APIRequestLog table to produce
    usage statistics. Does not write any additional records.
    """

    def get_today_usage(
        self, db: Session, service: str = "ebay"
    ) -> Dict:
        """
        Get API usage statistics for the last 24 hours.

        Args:
            db: Database session
            service: Service name filter (default "ebay")

        Returns:
            Dict with usage statistics
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        # Total API requests (non-cached)
        api_requests = (
            db.query(func.count(APIRequestLog.id))
            .filter(
                APIRequestLog.service == service,
                APIRequestLog.created_at >= cutoff,
                APIRequestLog.was_cached == False,  # noqa: E712
            )
            .scalar()
            or 0
        )

        # Successful requests
        successful = (
            db.query(func.count(APIRequestLog.id))
            .filter(
                APIRequestLog.service == service,
                APIRequestLog.created_at >= cutoff,
                APIRequestLog.was_cached == False,  # noqa: E712
                APIRequestLog.error_occurred == False,  # noqa: E712
            )
            .scalar()
            or 0
        )

        # Failed requests
        failed = (
            db.query(func.count(APIRequestLog.id))
            .filter(
                APIRequestLog.service == service,
                APIRequestLog.created_at >= cutoff,
                APIRequestLog.was_cached == False,  # noqa: E712
                APIRequestLog.error_occurred == True,  # noqa: E712
            )
            .scalar()
            or 0
        )

        # Cache hits
        cache_hits = (
            db.query(func.count(APIRequestLog.id))
            .filter(
                APIRequestLog.service == service,
                APIRequestLog.created_at >= cutoff,
                APIRequestLog.was_cached == True,  # noqa: E712
            )
            .scalar()
            or 0
        )

        # Total requests including cache hits
        total_requests = api_requests + cache_hits
        cache_misses = api_requests  # Non-cached = cache miss

        cache_hit_rate = (
            (cache_hits / total_requests * 100)
            if total_requests > 0
            else 0.0
        )

        # Average response time
        avg_response = (
            db.query(func.avg(APIRequestLog.response_time_ms))
            .filter(
                APIRequestLog.service == service,
                APIRequestLog.created_at >= cutoff,
                APIRequestLog.was_cached == False,  # noqa: E712
                APIRequestLog.response_time_ms.isnot(None),
            )
            .scalar()
        )

        return {
            "period": "24h",
            "api_requests": api_requests,
            "successful_requests": successful,
            "failed_requests": failed,
            "cache_hits": cache_hits,
            "cache_misses": cache_misses,
            "cache_hit_rate": round(cache_hit_rate, 1),
            "total_requests": total_requests,
            "avg_response_time_ms": (
                round(float(avg_response), 1) if avg_response else None
            ),
        }

    def get_usage_by_endpoint(
        self, db: Session, service: str = "ebay", hours: int = 24
    ) -> Dict[str, int]:
        """
        Get request counts grouped by endpoint.

        Args:
            db: Database session
            service: Service name filter
            hours: Time window in hours

        Returns:
            Dict mapping endpoint → request count
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        rows = (
            db.query(
                APIRequestLog.endpoint,
                func.count(APIRequestLog.id),
            )
            .filter(
                APIRequestLog.service == service,
                APIRequestLog.created_at >= cutoff,
            )
            .group_by(APIRequestLog.endpoint)
            .all()
        )

        return {endpoint: count for endpoint, count in rows}

    def log_cache_event(
        self,
        db: Session,
        event_type: str,
        endpoint: str,
        marketplace: str = "EBAY_US",
        cache_key: Optional[str] = None,
        response_time_ms: Optional[int] = None,
    ) -> None:
        """
        Log a cache event to APIRequestLog.

        Event types: CACHE_HIT, CACHE_MISS, CACHE_STALE, RETRY

        Args:
            db: Database session
            event_type: Event type string
            endpoint: API endpoint
            marketplace: Marketplace ID
            cache_key: Cache key if applicable
            response_time_ms: Response time if applicable
        """
        try:
            is_cache_hit = event_type in ("CACHE_HIT", "CACHE_STALE")

            log_entry = APIRequestLog(
                service="ebay",
                endpoint=endpoint,
                method="CACHE",
                status_code=200 if is_cache_hit else None,
                response_time_ms=response_time_ms,
                was_cached=is_cache_hit,
                cache_key=cache_key,
                error_occurred=(event_type in ("CACHE_STALE", "RETRY")),
                error_message=event_type,
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to log cache event: {e}")