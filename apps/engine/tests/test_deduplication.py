"""Tests for ProductDeduplicator."""
from decimal import Decimal

import pytest

from services.search.deduplication import ProductDeduplicator


class TestProductDeduplicator:
    @pytest.fixture
    def deduper(self):
        return ProductDeduplicator()

    def _listing(
        self, title, item_id="v1|001|0", price=29.99,
        seller="seller1", sold=None
    ):
        return {
            "item_id": item_id,
            "title": title,
            "price_value": Decimal(str(price)),
            "price_currency": "USD",
            "seller_username": seller,
            "estimated_sold_quantity": sold,
            "condition": "New",
        }

    def test_empty_list(self, deduper):
        assert deduper.deduplicate([]) == []

    def test_single_listing(self, deduper):
        listings = [self._listing("Wireless Bluetooth Earbuds")]
        groups = deduper.deduplicate(listings)
        assert len(groups) == 1
        assert groups[0].seller_count == 1

    def test_duplicate_listings_grouped(self, deduper):
        listings = [
            self._listing(
                "Wireless Bluetooth Earbuds TWS", "v1|1|0",
                29.99, "seller1"
            ),
            self._listing(
                "Wireless Bluetooth Earbuds TWS", "v1|2|0",
                31.99, "seller2"
            ),
            self._listing(
                "Wireless Bluetooth Earbuds TWS Noise", "v1|3|0",
                28.99, "seller3"
            ),
        ]
        groups = deduper.deduplicate(listings)
        # Should group into fewer groups than original listings
        assert len(groups) < len(listings)

    def test_different_products_not_grouped(self, deduper):
        listings = [
            self._listing("Apple AirPods Pro 2", "v1|1|0"),
            self._listing("Samsung Galaxy Buds Pro", "v1|2|0"),
        ]
        groups = deduper.deduplicate(listings)
        # Different brands → different groups
        assert len(groups) == 2

    def test_different_storage_variants_separate(self, deduper):
        listings = [
            self._listing("iPhone 15 128GB", "v1|1|0"),
            self._listing("iPhone 15 256GB", "v1|2|0"),
        ]
        groups = deduper.deduplicate(listings)
        # Different storage = different variants = separate groups
        assert len(groups) == 2

    def test_seller_count_tracked(self, deduper):
        listings = [
            self._listing("Earbuds", "v1|1|0", 29.99, "seller_a"),
            self._listing("Earbuds", "v1|2|0", 31.99, "seller_b"),
            self._listing("Earbuds", "v1|3|0", 28.99, "seller_c"),
        ]
        groups = deduper.deduplicate(listings)
        # All same product → one group with 3 sellers
        assert any(g.seller_count == 3 for g in groups)

    def test_price_range_tracked(self, deduper):
        listings = [
            self._listing("Earbuds", "v1|1|0", 20.00, "s1"),
            self._listing("Earbuds", "v1|2|0", 35.00, "s2"),
        ]
        groups = deduper.deduplicate(listings)
        group = groups[0]
        assert group.price_min == Decimal("20.00")
        assert group.price_max == Decimal("35.00")

    def test_best_representative_by_sold(self, deduper):
        listings = [
            self._listing("Earbuds", "v1|1|0", 30, "s1", sold=10),
            self._listing("Earbuds", "v1|2|0", 30, "s2", sold=100),
            self._listing("Earbuds", "v1|3|0", 30, "s3", sold=5),
        ]
        groups = deduper.deduplicate(listings)
        # Best representative should be the one with highest sold
        rep = groups[0].representative
        assert rep["estimated_sold_quantity"] == 100

    def test_to_dict(self, deduper):
        listings = [self._listing("Earbuds")]
        groups = deduper.deduplicate(listings)
        d = groups[0].to_dict()
        assert "product_key" in d
        assert "listing_count" in d
        assert "seller_count" in d
        assert "price_range" in d