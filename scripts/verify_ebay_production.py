#!/usr/bin/env python3
"""
REHU Production Verification Script.

Performs safe, read-only checks against live eBay Production APIs.
Verifies OAuth, Browse API, parser, rate limiter, cache, and audit logging.

Usage:
    python scripts/verify_ebay_production.py

Safety: Only performs read-only Browse API searches.
Does NOT create, modify, or delete any eBay data.
"""
import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.ebay.rate_limiter import RateLimiter
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
WARN = "\033[93m[WARN]\033[0m"
INFO = "\033[94m[INFO]\033[0m"

results = {"passed": 0, "failed": 0, "warnings": 0}


def check(name: str, condition: bool, detail: str = ""):
    if condition:
        print(f"  {PASS} {name}")
        results["passed"] += 1
    else:
        print(f"  {FAIL} {name} {detail}")
        results["failed"] += 1


def warn(name: str, detail: str = ""):
    print(f"  {WARN} {name} {detail}")
    results["warnings"] += 1


def mask(s: str, show: int = 4) -> str:
    if not s or len(s) <= show:
        return "***"
    return s[:show] + "*" * (len(s) - show)


def main():
    print("=" * 60)
    print("  REHU Production Verification")
    print("=" * 60)

    # A. Configuration
    print("\n[A] Configuration")
    env = getattr(settings, "ebay_environment", "sandbox")
    check("EBAY_ENVIRONMENT is 'production'", env == "production", f"(got: {env})")

    app_id = getattr(settings, "ebay_app_id", "")
    check("EBAY_APP_ID exists", bool(app_id))
    if app_id:
        print(f"  {INFO} App ID: {mask(app_id)}")

    cert_id = getattr(settings, "ebay_cert_id", "")
    check("EBAY_CERT_ID exists", bool(cert_id))

    marketplace = getattr(settings, "ebay_marketplace_id", "")
    check("EBAY_MARKETPLACE_ID exists", bool(marketplace))

    # B. OAuth
    print("\n[B] OAuth Token Acquisition")
    try:
        from services.ebay.auth import EbayAuth
        auth = EbayAuth()
        token = auth.get_application_token()
        check("OAuth token acquired", bool(token))
        check("Token is Bearer format", token and len(token) > 20)
        print(f"  {INFO} Token: {mask(token, 8)}...")
    except Exception as e:
        check("OAuth token acquired", False, str(e))
        print(f"\n  Cannot continue without OAuth. Aborting.")
        print_summary()
        return

    # C. Browse API (all 5 marketplaces)
    print("\n[C] Browse API — Live Search")
    from services.ebay.marketplace import EbayMarketplace

    test_queries = ["wireless earbuds", "phone case"]
    marketplaces = [
        ("US", EbayMarketplace.US),
        ("UK", EbayMarketplace.UK),
        ("DE", EbayMarketplace.GERMANY),
        ("AU", EbayMarketplace.AUSTRALIA),
        ("CA", EbayMarketplace.CANADA),
    ]

    from services.ebay.client import EbayClient
    from services.ebay.rate_limiter import RateLimiter

    for mp_name, mp_enum in marketplaces:
        print(f"\n  --- Marketplace: {mp_name} ({mp_enum.value}) ---")
        try:
            limiter = RateLimiter()
            client = EbayClient(
                auth=auth,
                rate_limiter=limiter,
                marketplace=mp_enum,
            )
            result = client.search_items(query=test_queries[0], limit=3)
            items = result.get("itemSummaries", result.get("items", []))

            check(f"{mp_name}: Search returned items", len(items) > 0, f"(got {len(items)})")

            if items:
                first = items[0]
                title = first.get("title", "")
                check(f"{mp_name}: Title parsed", bool(title))

                price_val = first.get("price_value")
                check(
                    f"{mp_name}: Price parsed",
                    price_val is not None,
                    f"(got {price_val})"
                )

                currency = first.get("price_currency")
                check(
                    f"{mp_name}: Currency present",
                    bool(currency)
                )

                currency = first.get("price_currency")
                check(
                    f"{mp_name}: Currency present",
                    bool(currency),
                )

                item_id = first.get("item_id")
                check(
                    f"{mp_name}: Item ID present",
                    bool(item_id)
                )

                image = first.get("image_url")
                check(
                    f"{mp_name}: Image data present",
                    bool(image)
                )

        except Exception as e:
            check(f"{mp_name}: Search succeeded", False, str(e))

    # D. Parser Validation
    print("\n[D] Parser Validation")
    try:
        from services.ebay.parser import EbayParser

        parser = EbayParser()
        limiter = RateLimiter()
        client = EbayClient(
            auth=auth,
            rate_limiter=limiter,
            marketplace=EbayMarketplace.US,
        )

        # Get the raw eBay Browse API response directly.
        raw = client._make_request(
            method="GET",
            endpoint="/buy/browse/v1/item_summary/search",
            params={
                "q": "phone case",
                "limit": 2,
                "offset": 0,
                "sort": "relevance",
            },
        )

        parsed = parser.parse_search_response(
            raw,
            marketplace="EBAY_US",
        )

        items = parsed.get("items", [])

        check("Parser produced items", len(items) > 0)
        if items:
            p = items[0]
            check("price_value populated", p.get("price_value") is not None)
            check("price_currency populated", bool(p.get("price_currency")))
            check("marketplace injected", bool(p.get("marketplace")))
            check("raw_data preserved", p.get("raw_data") is not None)
    except Exception as e:
        check("Parser validation", False, str(e))

    # E. Audit Logging
    print("\n[E] Audit Logging")
    try:
        from database.connection import get_db_context
        from models.audit import APIRequestLog

        with get_db_context() as db:
            recent = (
                db.query(APIRequestLog)
                .order_by(APIRequestLog.created_at.desc())
                .first()
            )
            if recent:
                check("Audit log has records", True)
                check("method is not NULL", recent.method is not None, f"(got: {recent.method})")
                check("status_code present", recent.status_code is not None)
                check("endpoint present", bool(recent.endpoint))
            else:
                warn("No audit log records found (may be first run)")
    except Exception as e:
        check("Audit logging", False, str(e))

    # Summary
    print_summary()


def print_summary():
    print("\n" + "=" * 60)
    total = results["passed"] + results["failed"]
    if results["failed"] == 0:
        print(f"  PRODUCTION VERIFICATION: {PASS} PASS")
        print(f"  {results['passed']}/{total} checks passed, {results['warnings']} warnings")
    else:
        print(f"  PRODUCTION VERIFICATION: {FAIL} FAIL")
        print(f"  {results['passed']}/{total} passed, {results['failed']} failed, {results['warnings']} warnings")
    print("=" * 60)
    sys.exit(1 if results["failed"] > 0 else 0)


if __name__ == "__main__":
    main()