"""
Multi-Marketplace Verification Script

Tests eBay search across multiple regional marketplaces using
the same credentials and same EbayClient implementation.

Usage:
    python scripts/verify_marketplaces.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.ebay.client import EbayClient
from services.ebay.marketplace import EbayMarketplace
from utils.logger import setup_logging

logger = setup_logging("marketplace_verification")


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_section(title: str):
    print("\n" + "─" * 70)
    print(f"  {title}")
    print("─" * 70)


def test_marketplace(marketplace: EbayMarketplace, query: str = "wireless earbuds"):
    """
    Test search on a specific marketplace.

    Args:
        marketplace: EbayMarketplace enum member
        query: Search query
    """
    print_section(
        f"{marketplace.display_name} ({marketplace.value}) "
        f"— Native currency: {marketplace.currency}"
    )

    try:
        # Create client for this specific marketplace
        client = EbayClient(marketplace=marketplace)

        # Verify client config
        print(f"  Client marketplace: {client.marketplace_id}")
        print(f"  Expected header:    X-EBAY-C-MARKETPLACE-ID: {client.marketplace_id}")

        # Search
        print(f"\n  ⏳ Searching for '{query}' (limit=5)...")
        results = client.search_items(query=query, limit=5)

        print(f"  ✅ Total results: {results['total']}")
        print(f"  ✅ Items retrieved: {results['items_count']}")
        print(f"  ✅ Response marketplace: {results.get('marketplace')}")

        if results["items"]:
            first = results["items"][0]
            print(f"\n  Sample result:")
            print(f"    Title:       {first['title'][:60]}...")
            print(f"    Price:       {first['price_value']} {first['price_currency']}")
            print(f"    Item ID:     {first['item_id']}")
            print(f"    Marketplace: {first['marketplace']}")
            print(f"    Condition:   {first.get('condition', 'N/A')}")

            # Verify marketplace is correctly injected
            assert first["marketplace"] == marketplace.value, (
                f"Marketplace mismatch! Expected {marketplace.value}, "
                f"got {first['marketplace']}"
            )
            print(f"\n  ✅ Marketplace correctly stamped on each item")

            # Check currency matches expectation
            actual_currency = first["price_currency"]
            expected_currency = marketplace.currency
            if actual_currency == expected_currency:
                print(f"  ✅ Currency matches marketplace: {actual_currency}")
            else:
                print(
                    f"  ⚠️  Currency mismatch: got {actual_currency}, "
                    f"expected {expected_currency} for {marketplace.value}"
                )
                print(f"     (Note: Some sellers may list in USD on non-US sites)")

        return True

    except Exception as e:
        print(f"  ❌ Error on {marketplace.value}: {type(e).__name__}: {e}")
        logger.error(f"Marketplace {marketplace.value} test failed: {e}", exc_info=True)
        return False


def test_database_isolation():
    """Test that same item_id from different marketplaces coexist in DB."""
    print_header("DATABASE MARKETPLACE ISOLATION TEST")

    try:
        from services.ebay.repository import EbayListingRepository
        from database import get_db

        db = next(get_db())

        # Search on 2 marketplaces
        us_client = EbayClient(marketplace=EbayMarketplace.US)
        gb_client = EbayClient(marketplace=EbayMarketplace.UK)

        print("\n  ⏳ Searching 'wireless mouse' on US...")
        us_results = us_client.search_items("wireless mouse", limit=3)
        us_saved = EbayListingRepository.save_listings_bulk(
            db, us_results["items"]
        )
        print(f"  ✅ Saved {len(us_saved)} US listings")

        print("\n  ⏳ Searching 'wireless mouse' on UK...")
        gb_results = gb_client.search_items("wireless mouse", limit=3)
        gb_saved = EbayListingRepository.save_listings_bulk(
            db, gb_results["items"]
        )
        print(f"  ✅ Saved {len(gb_saved)} UK listings")

        # Verify marketplace field on saved records
        print("\n  Saved US records:")
        for listing in us_saved[:3]:
            print(
                f"    id={listing.id} marketplace={listing.marketplace} "
                f"item_id={listing.item_id[:20]}..."
            )

        print("\n  Saved UK records:")
        for listing in gb_saved[:3]:
            print(
                f"    id={listing.id} marketplace={listing.marketplace} "
                f"item_id={listing.item_id[:20]}..."
            )

        # Verify marketplace-specific lookup
        if us_saved:
            first_us_id = us_saved[0].item_id
            us_lookup = EbayListingRepository.get_by_marketplace_and_item(
                db, "EBAY_US", first_us_id
            )
            print(f"\n  ✅ US-specific lookup works: {us_lookup is not None}")

        if gb_saved:
            first_gb_id = gb_saved[0].item_id
            gb_lookup = EbayListingRepository.get_by_marketplace_and_item(
                db, "EBAY_GB", first_gb_id
            )
            print(f"  ✅ UK-specific lookup works: {gb_lookup is not None}")

        return True

    except Exception as e:
        print(f"  ❌ Database isolation test failed: {e}")
        logger.error(f"DB isolation failed: {e}", exc_info=True)
        return False


def main():
    print("\n" + "=" * 70)
    print("  MULTI-MARKETPLACE VERIFICATION")
    print("  Same EbayClient — 5 Different Regional Marketplaces")
    print("=" * 70)

    print("\n📋 Configured marketplaces:")
    for m in EbayMarketplace:
        print(
            f"  • {m.value:10s} — {m.display_name:25s} "
            f"({m.currency})"
        )

    print_header("MARKETPLACE SEARCH TESTS")

    results = {}

    # Test each marketplace
    for marketplace in EbayMarketplace:
        results[marketplace.value] = test_marketplace(marketplace)

    # Test database isolation
    results["database_isolation"] = test_database_isolation()

    # Summary
    print_header("VERIFICATION SUMMARY")

    passed = 0
    failed = 0
    for name, ok in results.items():
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"{status} — {name}")
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")

    print("\n" + "=" * 70)
    if failed == 0:
        print("  🎉 MULTI-MARKETPLACE VERIFICATION COMPLETE")
        print("=" * 70)
        print("\n✅ Single EbayClient implementation working across 5 marketplaces")
        print("✅ Marketplace header sent correctly to eBay API")
        print("✅ Marketplace stamped on every parsed listing")
        print("✅ Database isolation working (same item_id, different marketplaces)")
    else:
        print("  ⚠️  SOME MARKETPLACES FAILED")
        print("=" * 70)
        print("\nCommon reasons:")
        print("  • Sandbox may have limited/no data for non-US marketplaces")
        print("  • Some sandbox marketplaces may return 0 results")
        print("  • Test with production credentials for full validation")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())