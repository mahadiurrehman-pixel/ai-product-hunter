"""Tests for QueryParser and SearchIntent."""
import pytest

from services.search.query_parser import QueryParser, SearchIntent


class TestQueryParser:
    @pytest.fixture
    def parser(self):
        return QueryParser()

    # --- Basic parsing ---

    def test_empty_query(self, parser):
        intent = parser.parse("")
        assert intent.raw_query == ""
        assert intent.normalized_query == ""
        assert intent.product_type is None

    def test_simple_query(self, parser):
        intent = parser.parse("wireless earbuds")
        assert intent.raw_query == "wireless earbuds"
        assert "wireless" in intent.keywords
        assert "earbuds" in intent.keywords

    # --- Product type detection ---

    def test_earbuds_detected(self, parser):
        intent = parser.parse("wireless earbuds")
        assert intent.product_type == "earbuds"
        assert intent.category == "audio"

    def test_headphones_detected(self, parser):
        intent = parser.parse("bluetooth headphones")
        assert intent.product_type == "headphones"

    def test_keyboard_not_audio(self, parser):
        """bluetooth keyboard must NOT be classified as audio."""
        intent = parser.parse("bluetooth keyboard")
        assert intent.product_type == "keyboard"
        assert intent.category == "peripherals"

    def test_phone_case_detected(self, parser):
        intent = parser.parse("iphone case")
        assert intent.product_type == "phone_case"

    def test_charger_detected(self, parser):
        intent = parser.parse("usb c fast charger")
        assert intent.product_type == "charger"

    def test_laptop_detected(self, parser):
        intent = parser.parse("gaming laptop")
        assert intent.product_type == "laptop"

    def test_mouse_detected(self, parser):
        intent = parser.parse("wireless mouse")
        assert intent.product_type == "mouse"

    def test_smartwatch_detected(self, parser):
        intent = parser.parse("fitness tracker watch")
        assert intent.product_type in ("smartwatch", "watch")

    # --- Brand detection ---

    def test_apple_brand(self, parser):
        intent = parser.parse("Apple AirPods Pro")
        assert intent.brand == "Apple"

    def test_samsung_brand(self, parser):
        intent = parser.parse("Samsung Galaxy S24")
        assert intent.brand == "Samsung"

    def test_nike_brand(self, parser):
        intent = parser.parse("Nike Air Max shoes")
        assert intent.brand == "Nike"

    def test_sony_brand(self, parser):
        intent = parser.parse("Sony WH-1000XM5")
        assert intent.brand == "Sony"

    def test_no_brand(self, parser):
        intent = parser.parse("wireless earbuds cheap")
        assert intent.brand is None

    # --- Model detection ---

    def test_iphone_model(self, parser):
        intent = parser.parse("iPhone 15 Pro Max case")
        assert intent.model is not None
        assert "15" in intent.model.lower()

    def test_galaxy_model(self, parser):
        intent = parser.parse("Galaxy S24 Ultra screen protector")
        assert intent.model is not None
        assert "s24" in intent.model.lower()

    # --- Condition ---

    def test_new_condition(self, parser):
        intent = parser.parse("new wireless earbuds")
        assert intent.condition == "new"

    def test_used_condition(self, parser):
        intent = parser.parse("used iPhone 15")
        assert intent.condition == "used"

    def test_refurbished_condition(self, parser):
        intent = parser.parse("refurbished laptop")
        assert intent.condition == "refurbished"

    def test_no_condition(self, parser):
        intent = parser.parse("wireless earbuds")
        assert intent.condition is None

    # --- Aliases ---

    def test_airpods_alias(self, parser):
        intent = parser.parse("air pods pro")
        assert "airpods" in intent.normalized_query

    def test_usb_c_alias(self, parser):
        intent = parser.parse("usb c charger")
        assert "usb-c" in intent.normalized_query

    # --- Attributes ---

    def test_bluetooth_attribute(self, parser):
        intent = parser.parse("bluetooth speaker 20W")
        assert "connectivity" in intent.attributes
        assert intent.attributes["connectivity"] == "bluetooth"

    def test_wattage_attribute(self, parser):
        intent = parser.parse("20W USB-C charger")
        assert "wattage" in intent.attributes
        assert "20" in intent.attributes["wattage"]

    # --- Exclusions ---

    def test_exclusion_detected(self, parser):
        intent = parser.parse("wireless earbuds not refurbished")
        assert "refurbished" in intent.exclusions

    # --- SearchIntent to_dict ---

    def test_to_dict(self, parser):
        intent = parser.parse("Apple AirPods Pro 2")
        d = intent.to_dict()
        assert "raw_query" in d
        assert "brand" in d
        assert "product_type" in d
        assert "keywords" in d

    # --- Edge cases ---

    def test_very_short_query(self, parser):
        intent = parser.parse("tv")
        assert intent.raw_query == "tv"
        assert len(intent.keywords) >= 1

    def test_special_characters(self, parser):
        intent = parser.parse("USB-C hub 7-in-1!")
        assert "usb-c" in intent.normalized_query or "usb" in intent.normalized_query


class TestSearchIntentDataclass:
    def test_defaults(self):
        intent = SearchIntent(raw_query="test", normalized_query="test")
        assert intent.product_type is None
        assert intent.brand is None
        assert intent.keywords == []
        assert intent.exclusions == []