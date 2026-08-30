from models.product import NormalizedProduct
from models.ebay import EbayListing
from models.aliexpress import AliExpressListing


def test_normalized_product_model_exists():
    assert NormalizedProduct.__tablename__ == "normalized_products"


def test_ebay_listing_model_exists():
    assert EbayListing.__tablename__ == "ebay_listings"


def test_aliexpress_listing_model_exists():
    assert AliExpressListing.__tablename__ == "aliexpress_listings"


def test_database_session_works(db_session):
    assert db_session is not None


def test_sample_ebay_fixture(sample_ebay_item):
    assert sample_ebay_item["itemId"] == "v1|123456789|0"
    assert sample_ebay_item["price"]["currency"] == "USD"
    assert sample_ebay_item["condition"] == "New"


def test_sample_aliexpress_fixture(sample_aliexpress_product):
    assert sample_aliexpress_product["product_id"] == "1234567890"
    assert sample_aliexpress_product["price"]["currency"] == "USD"
    assert sample_aliexpress_product["rating"]["score"] == 4.8
