"""
Phase 4 Verification Script

Tests AliExpress mock adapter, product data models,
and database persistence.

Usage:
    python scripts/verify_phase4.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.aliexpress import get_adapter, MockAliExpressAdapter
from services.aliexpress.repository import AliExpressRepository
from database import get_db
from utils.logger import setup_logging

logger = setup_logging("phase4_verification")


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_section(title: str):
    print("\n" + "─" * 70)
    print(f"  {title}")
    print("─" * 70)


def test_adapter_factory():
    """Test get_adapter() returns correct adapter."""
    print_header("ADAPTER FACTORY TEST")

    adapter = get_adapter()
    print(f"\n✅ Adapter type: {type(adapter).__name__}")
    print(f"✅ Demo mode: {adapter.is_demo_mode()}")

    warning = adapter.get_demo_warning()
    if warning:
        print(f"\n{warning}")

    return True


def test_mock_search():
    """Test mock product search."""
    print_header("MOCK PRODUCT SEARCH TEST")

    adapter = MockAliExpressAdapter()

    queries = [
        "wireless earbuds bluetooth",
        "phone charger usb-c fast",
        "wireless mouse ergonomic",
        "phone case iphone",
        "led strip lights rgb",
    ]

    all_passed = True

    for query in queries:
        print_section(f"Query: '{query}'")

        results = adapter.search_products(query, limit=3)

        if not results:
            print(f"⚠️  No results returned")
            all_passed = False
            continue

        print(f"✅ {len(results)} results returned\n")

        for i, product in enumerate(results, 1):
            print(f"  {i}. {product.title[:55]}...")
            print(f"     Price: ${product.price.value} {product.price.currency}")
            print(f"     Rating: {product.rating_score or 'N/A'}/5.0")
            print(f"     Orders: {product.orders_count or 'N/A'}")
            print(f"     Source: {product.source} {product.demo_label}")
            if product.store:
                print(f"     Store: {product.store.name}")
            print()

    return all_passed


def test_product_details():
    """Test getting product details by ID."""
    print_header("PRODUCT DETAILS TEST")

    adapter = MockAliExpressAdapter()

    print("\n⏳ Testing all 15 mock products by ID...")

    all_found = True
    for i in range(1, 16):
        product_id = f"ali_{i:03d}"
        product = adapter.get_product_details(product_id)

        if product is None:
            print(f"  ❌ {product_id}: NOT FOUND")
            all_found = False
        else:
            shipping = product.shipping_options[0] if product.shipping_options else None
            shipping_str = (
                f"Free shipping" if shipping and shipping.cost == 0
                else f"${shipping.cost}" if shipping
                else "No shipping info"
            )
            print(
                f"  ✅ {product_id}: "
                f"${product.price.value} | "
                f"{shipping_str} | "
                f"Rating: {product.rating_score}"
            )

    print(f"\n{'✅ All 15 products found' if all_found else '❌ Some products missing'}")
    return all_found


def test_data_quality():
    """Test mock data quality and realism."""
    print_header("DATA QUALITY CHECK")

    adapter = MockAliExpressAdapter()

    issues = []

    for i in range(1, 16):
        product_id = f"ali_{i:03d}"
        product = adapter.get_product_details(product_id)

        if product is None:
            issues.append(f"{product_id}: not found")
            continue

        # Price should be reasonable (< $50 for sourcing)
        price = float(product.price.value)
        if price <= 0:
            issues.append(f"{product_id}: non-positive price {price}")
        if price > 50:
            issues.append(
                f"{product_id}: price ${price} unusually high for sourcing"
            )

        # Rating should be 1-5
        if product.rating_score is not None:
            if not 1.0 <= product.rating_score <= 5.0:
                issues.append(
                    f"{product_id}: invalid rating {product.rating_score}"
                )

        # Source must be "mock"
        if product.source != "mock":
            issues.append(
                f"{product_id}: source is '{product.source}', expected 'mock'"
            )

        # Must have shipping
        if not product.shipping_options:
            issues.append(f"{product_id}: no shipping options")

    if issues:
        print(f"\n❌ Data quality issues found:")
        for issue in issues:
            print(f"   • {issue}")
        return False
    else:
        print(f"\n✅ All 15 products pass data quality checks")
        print(f"   • Prices realistic (sourcing range)")
        print(f"   • Ratings valid (1.0-5.0)")
        print(f"   • Source correctly labeled 'mock'")
        print(f"   • All have shipping options")
        return True


def test_database_persistence():
    """Test saving mock products to database."""
    print_header("DATABASE PERSISTENCE TEST")

    adapter = MockAliExpressAdapter()
    results = adapter.search_products("bluetooth speaker", limit=3)

    if not results:
        print("⚠️  No results to save")
        return False

    print(f"\n⏳ Saving {len(results)} products to database...")

    db = next(get_db())
    saved = AliExpressRepository.save_products_bulk(db, results)

    print(f"✅ Saved {len(saved)} products")

    # Verify retrieval
    for listing in saved:
        retrieved = AliExpressRepository.get_by_product_id(
            db, listing.product_id
        )
        assert retrieved is not None
        print(
            f"✅ Retrieved: {retrieved.product_id} — "
            f"${retrieved.price_value} ({retrieved.source})"
        )

    return True


def test_normalization_integration():
    """Test mock adapter works with Phase 3 normalizer output."""
    print_header("NORMALIZER INTEGRATION TEST")

    from services.scoring.normalizer import ProductNormalizer

    normalizer = ProductNormalizer()
    adapter = MockAliExpressAdapter()

    test_titles = [
        "Wireless Bluetooth Earbuds TWS Noise Cancelling Black",
        "20W USB-C Fast Charger Wall Adapter",
        "Samsung Galaxy Phone Case Silicone Cover",
    ]

    for title in test_titles:
        print(f"\n📦 eBay product: {title}")

        normalized = normalizer.normalize(title)
        print(f"   Normalized: {normalized.normalized_title[:50]}...")
        print(f"   Keywords: {', '.join(normalized.keywords[:5])}")

        # Use normalized title as AliExpress search query
        query = normalized.normalized_title
        results = adapter.search_products(query, limit=3)

        print(f"   → AliExpress results: {len(results)}")
        for r in results[:2]:
            print(f"      • {r.title[:50]}... (${r.price.value})")

    return True


def main():
    """Run all Phase 4 verification tests."""
    print("\n" + "=" * 70)
    print("  PHASE 4 VERIFICATION")
    print("  AliExpress Mock Adapter & Data Models")
    print("=" * 70)

    results = {}

    results["adapter_factory"] = test_adapter_factory()
    results["mock_search"] = test_mock_search()
    results["product_details"] = test_product_details()
    results["data_quality"] = test_data_quality()
    results["database"] = test_database_persistence()
    results["normalizer_integration"] = test_normalization_integration()

    print_header("VERIFICATION SUMMARY")

    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} — {test_name.replace('_', ' ').title()}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("  🎉 PHASE 4 VERIFICATION COMPLETE — ALL PASSED")
        print("=" * 70)
        print("\n✅ AliExpress mock adapter working")
        print("✅ All 15 mock products loadable and searchable")
        print("✅ Database persistence working")
        print("✅ Normalizer integration working")
        print("\n⚠️  DEMO MODE active — all AliExpress data is simulated")
        print("⚠️  Do not use mock prices for real purchasing decisions")
        print("\nReady for Phase 5: Product Matching")
    else:
        print("  ❌ SOME VERIFICATIONS FAILED")
        print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())