"""
Tests for AliExpress repository (database persistence).
"""
import pytest
from decimal import Decimal

from services.aliexpress.models import (
    AliExpressPrice,
    AliExpressProduct,
    AliExpressStore,
    AliExpressShipping,
)
from services.aliexpress.repository import AliExpressRepository
from models.aliexpress import AliExpressListing


class TestAliExpressRepository:
    """Test AliExpress repository database operations."""

    @pytest.fixture
    def sample_product(self):
        """Sample AliExpressProduct for testing."""
        return AliExpressProduct(
            product_id="test_ali_001",
            title="Test TWS Wireless Earbuds",
            price=AliExpressPrice(
                value=Decimal("8.99"),
                currency="USD",
                original_value=Decimal("12.99"),
            ),
            product_url="https://www.aliexpress.com/item/test_001.html",
            source="mock",
            image_url="https://example.com/image.jpg",
            store=AliExpressStore(
                name="Test Store",
                store_id="test_store_001",
                url="https://www.aliexpress.com/store/test_store_001",
            ),
            rating_score=4.8,
            review_count=1234,
            orders_count=5678,
            attributes={"color": "black", "connectivity": "bluetooth"},
            shipping_options=[
                AliExpressShipping(
                    method="AliExpress Standard Shipping",
                    cost=Decimal("0.00"),
                    estimated_days_min=15,
                    estimated_days_max=30,
                )
            ],
        )

    @pytest.fixture
    def sample_product_2(self):
        """Second sample product for bulk testing."""
        return AliExpressProduct(
            product_id="test_ali_002",
            title="Test USB-C Fast Charger",
            price=AliExpressPrice(
                value=Decimal("3.50"),
                currency="USD",
            ),
            product_url="https://www.aliexpress.com/item/test_002.html",
            source="mock",
            rating_score=4.5,
            review_count=987,
            orders_count=3210,
        )

    def test_save_product_creates_record(
        self, db_session, sample_product
    ):
        """Test that save_product creates a new database record."""
        listing = AliExpressRepository.save_product(
            db_session, sample_product
        )

        assert listing is not None
        assert listing.id is not None
        assert listing.product_id == "test_ali_001"
        assert listing.title == "Test TWS Wireless Earbuds"
        assert listing.source == "mock"

    def test_save_product_price_stored_correctly(
        self, db_session, sample_product
    ):
        """Test price is stored correctly."""
        listing = AliExpressRepository.save_product(
            db_session, sample_product
        )

        assert float(listing.price_value) == 8.99
        assert listing.price_currency == "USD"
        assert float(listing.original_price_value) == 12.99

    def test_save_product_store_stored(
        self, db_session, sample_product
    ):
        """Test store information is stored."""
        listing = AliExpressRepository.save_product(
            db_session, sample_product
        )

        assert listing.store_name == "Test Store"
        assert listing.store_id == "test_store_001"

    def test_save_product_ratings_stored(
        self, db_session, sample_product
    ):
        """Test ratings are stored correctly."""
        listing = AliExpressRepository.save_product(
            db_session, sample_product
        )

        assert float(listing.rating_score) == 4.8
        assert listing.review_count == 1234
        assert listing.orders_count == 5678

    def test_save_product_upsert_updates_existing(
        self, db_session, sample_product
    ):
        """Test that saving same product_id updates existing record."""
        first = AliExpressRepository.save_product(
            db_session, sample_product
        )
        first_id = first.id

        # Modify and save again
        sample_product.price.value = Decimal("7.50")
        sample_product.title = "Updated Title"

        second = AliExpressRepository.save_product(
            db_session, sample_product
        )

        assert second.id == first_id  # Same record
        assert second.title == "Updated Title"
        assert float(second.price_value) == 7.50

        # Only one record should exist
        all_records = (
            db_session.query(AliExpressListing)
            .filter(
                AliExpressListing.product_id == "test_ali_001"
            )
            .all()
        )
        assert len(all_records) == 1

    def test_save_products_bulk(
        self, db_session, sample_product, sample_product_2
    ):
        """Test bulk save of multiple products."""
        saved = AliExpressRepository.save_products_bulk(
            db_session,
            [sample_product, sample_product_2],
        )

        assert len(saved) == 2
        ids = {s.product_id for s in saved}
        assert "test_ali_001" in ids
        assert "test_ali_002" in ids

    def test_get_by_product_id_found(
        self, db_session, sample_product
    ):
        """Test retrieval by product_id."""
        AliExpressRepository.save_product(db_session, sample_product)

        retrieved = AliExpressRepository.get_by_product_id(
            db_session, "test_ali_001"
        )

        assert retrieved is not None
        assert retrieved.product_id == "test_ali_001"

    def test_get_by_product_id_not_found(self, db_session):
        """Test retrieval of non-existent product returns None."""
        result = AliExpressRepository.get_by_product_id(
            db_session, "nonexistent_999"
        )
        assert result is None

    def test_get_by_source_mock(
        self, db_session, sample_product, sample_product_2
    ):
        """Test retrieval by source."""
        AliExpressRepository.save_products_bulk(
            db_session,
            [sample_product, sample_product_2],
        )

        mock_listings = AliExpressRepository.get_by_source(
            db_session, "mock"
        )

        assert len(mock_listings) >= 2
        for listing in mock_listings:
            assert listing.source == "mock"

    def test_save_minimal_product(self, db_session):
        """Test saving product with only required fields."""
        minimal = AliExpressProduct(
            product_id="test_minimal_001",
            title="Minimal Product",
            price=AliExpressPrice(value=Decimal("5.00")),
            product_url="https://www.aliexpress.com/item/minimal.html",
            source="mock",
        )

        listing = AliExpressRepository.save_product(db_session, minimal)

        assert listing is not None
        assert listing.product_id == "test_minimal_001"
        assert listing.store_name is None
        assert listing.rating_score is None