"""
Pytest configuration and fixtures.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from models.base import Base
from config import settings


@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Create test database session."""
    TestSessionLocal = sessionmaker(bind=test_engine)
    session = TestSessionLocal()

    yield session

    session.rollback()
    session.close()


@pytest.fixture
def sample_ebay_item():
    """Sample eBay item data."""
    return {
        "itemId": "v1|123456789|0",
        "title": "Wireless Bluetooth Earbuds with Charging Case",
        "price": {"value": "29.99", "currency": "USD"},
        "image": {"imageUrl": "https://example.com/image.jpg"},
        "itemWebUrl": "https://www.ebay.com/itm/123456789",
        "condition": "New",
        "categories": [{"categoryId": "15032", "categoryName": "Electronics"}],
        "seller": {
            "username": "seller123",
            "feedbackPercentage": "98.5",
            "feedbackScore": 1234,
        },
        "buyingOptions": ["FIXED_PRICE"],
        "shippingOptions": [
            {
                "shippingCostType": "FREE",
                "shippingCost": {"value": "0.00", "currency": "USD"},
            }
        ],
    }


@pytest.fixture
def sample_aliexpress_product():
    """Sample AliExpress product data."""
    return {
        "product_id": "1234567890",
        "title": "Wireless Bluetooth Earbuds TWS with Charging Box",
        "price": {"value": "12.50", "currency": "USD"},
        "image_url": "https://example.com/ali-image.jpg",
        "product_url": "https://www.aliexpress.com/item/1234567890.html",
        "store": {
            "name": "Tech Store Official",
            "id": "123456",
            "url": "https://www.aliexpress.com/store/123456",
        },
        "rating": {"score": 4.8, "review_count": 1523, "orders_count": 5234},
        "source": "mock",
    }
