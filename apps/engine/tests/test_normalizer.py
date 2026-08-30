"""
Tests for product normalization.
"""
import pytest
from services.scoring.normalizer import ProductNormalizer, NormalizedProduct


class TestProductNormalizer:
    """Test product text normalization and attribute extraction."""

    @pytest.fixture
    def normalizer(self):
        """Create normalizer instance."""
        return ProductNormalizer()

    def test_normalize_empty_title(self, normalizer):
        """Test handling of empty title."""
        result = normalizer.normalize("")
        assert result.normalized_title == ""
        assert result.brand is None
        assert len(result.keywords) == 0

    def test_normalize_whitespace_only(self, normalizer):
        """Test handling of whitespace-only title."""
        result = normalizer.normalize("   ")
        assert result.normalized_title == ""
        assert result.brand is None

    def test_clean_text_lowercase(self, normalizer):
        """Test text is converted to lowercase."""
        result = normalizer._clean_text("Apple iPhone 15 Pro Max")
        assert "apple" in result
        assert "iphone" in result
        assert "Apple" not in result

    def test_clean_text_removes_special_chars(self, normalizer):
        """Test special characters are removed."""
        result = normalizer._clean_text("iPhone 15 Pro - New!")
        assert "-" not in result
        assert "!" not in result
        assert "iphone" in result

    def test_clean_text_removes_stopwords(self, normalizer):
        """Test stopword removal."""
        result = normalizer._clean_text("Brand New Sealed iPhone")
        assert "brand" not in result
        assert "new" not in result
        assert "sealed" not in result
        assert "iphone" in result

    def test_clean_text_removes_extra_whitespace(self, normalizer):
        """Test extra whitespace is normalized."""
        result = normalizer._clean_text("iPhone    15    Pro")
        assert "  " not in result
        words = result.split()
        assert len([w for w in words if w == ""]) == 0

    def test_extract_brand_apple(self, normalizer):
        """Test Apple brand extraction."""
        brand = normalizer._extract_brand("Apple iPhone 15 Pro")
        assert brand == "Apple"

    def test_extract_brand_samsung(self, normalizer):
        """Test Samsung brand extraction."""
        brand = normalizer._extract_brand("Samsung Galaxy S23 Ultra")
        assert brand == "Samsung"

    def test_extract_brand_sony(self, normalizer):
        """Test Sony brand extraction."""
        brand = normalizer._extract_brand("Sony WH-1000XM5 Headphones")
        assert brand == "Sony"

    def test_extract_brand_case_insensitive(self, normalizer):
        """Test brand extraction is case insensitive."""
        brand = normalizer._extract_brand("APPLE iPhone")
        assert brand == "Apple"

        brand = normalizer._extract_brand("samsung phone")
        assert brand == "Samsung"

    def test_extract_brand_word_boundary(self, normalizer):
        """Test brand extraction uses word boundaries."""
        # "apple" in "pineapple" should NOT match
        brand = normalizer._extract_brand("Pineapple Juice")
        assert brand is None

    def test_extract_brand_not_found(self, normalizer):
        """Test when brand not in known list."""
        brand = normalizer._extract_brand("Generic Wireless Earbuds")
        assert brand is None

    def test_extract_color_black(self, normalizer):
        """Test black color extraction."""
        attrs = normalizer._extract_attributes("iPhone 15 Pro Black")
        assert "color" in attrs
        assert attrs["color"] == "black"

    def test_extract_color_space_gray(self, normalizer):
        """Test space gray color extraction."""
        attrs = normalizer._extract_attributes("iPhone 15 Space Gray")
        assert "color" in attrs
        assert "gray" in attrs["color"].lower()

    def test_extract_color_multiple_only_first(self, normalizer):
        """Test only first color is extracted."""
        attrs = normalizer._extract_attributes("Red and Blue Shirt")
        assert "color" in attrs
        # Should match first color found
        assert attrs["color"] in ["red", "blue"]

    def test_extract_storage_gb(self, normalizer):
        """Test GB storage extraction."""
        attrs = normalizer._extract_attributes("iPhone 15 256GB")
        assert "storage" in attrs
        assert attrs["storage"] == "256GB"

    def test_extract_storage_tb(self, normalizer):
        """Test TB storage extraction."""
        attrs = normalizer._extract_attributes("SSD 1TB")
        assert "storage" in attrs
        assert attrs["storage"] == "1TB"

    def test_extract_storage_with_space(self, normalizer):
        """Test storage extraction with space between number and unit."""
        attrs = normalizer._extract_attributes("iPhone 512 GB")
        assert "storage" in attrs
        assert "512" in attrs["storage"]
        assert "GB" in attrs["storage"]

    def test_extract_memory_ram(self, normalizer):
        """Test RAM extraction."""
        attrs = normalizer._extract_attributes("Laptop 16GB RAM")
        assert "memory" in attrs
        assert attrs["memory"] == "16GB"

    def test_extract_memory_alternative(self, normalizer):
        """Test memory extraction with 'memory' keyword."""
        attrs = normalizer._extract_attributes("Computer 32GB Memory")
        assert "memory" in attrs
        assert attrs["memory"] == "32GB"

    def test_extract_size_inches(self, normalizer):
        """Test size extraction in inches."""
        attrs = normalizer._extract_attributes('Samsung 55" TV')
        assert "size" in attrs
        assert "55" in attrs["size"]

    def test_extract_size_inch_word(self, normalizer):
        """Test size extraction with 'inch' word."""
        attrs = normalizer._extract_attributes("13 inch Laptop")
        assert "size" in attrs
        assert "13" in attrs["size"]

    def test_extract_size_decimal(self, normalizer):
        """Test size extraction with decimal."""
        attrs = normalizer._extract_attributes("6.7 inch Display")
        assert "size" in attrs
        assert "6.7" in attrs["size"]

    def test_extract_multiple_attributes(self, normalizer):
        """Test extraction of multiple attributes."""
        attrs = normalizer._extract_attributes(
            "Apple iPhone 15 Pro Max 256GB Space Gray 6.7 inch"
        )
        assert "storage" in attrs
        assert "color" in attrs
        assert "size" in attrs
        assert attrs["storage"] == "256GB"

    def test_extract_keywords_minimum_length(self, normalizer):
        """Test keywords are at least 3 characters."""
        keywords = normalizer._extract_keywords("iphone 15 pro")
        # "15" is 2 chars, should be excluded
        assert "15" not in keywords
        assert "iphone" in keywords
        assert "pro" in keywords

    def test_extract_keywords_no_digits(self, normalizer):
        """Test pure number keywords are excluded."""
        keywords = normalizer._extract_keywords("laptop 2023 256")
        assert "2023" not in keywords
        assert "256" not in keywords
        assert "laptop" in keywords

    def test_extract_keywords_deduplication(self, normalizer):
        """Test keywords are deduplicated."""
        keywords = normalizer._extract_keywords("iphone iphone case")
        assert keywords.count("iphone") == 1

    def test_extract_keywords_preserves_order(self, normalizer):
        """Test keyword order is preserved."""
        keywords = normalizer._extract_keywords("wireless bluetooth earbuds")
        assert keywords.index("wireless") < keywords.index("bluetooth")
        assert keywords.index("bluetooth") < keywords.index("earbuds")

    def test_extract_category_electronics(self, normalizer):
        """Test electronics category detection."""
        hints = normalizer._extract_category_hints("Apple iPhone 15 Pro")
        assert "electronics" in hints

    def test_extract_category_audio(self, normalizer):
        """Test audio category detection."""
        hints = normalizer._extract_category_hints(
            "Wireless Bluetooth Earbuds"
        )
        assert "audio" in hints

    def test_extract_category_accessories(self, normalizer):
        """Test accessories category detection."""
        hints = normalizer._extract_category_hints("iPhone Case Black")
        assert "accessories" in hints

    def test_extract_category_multiple(self, normalizer):
        """Test multiple category detection."""
        hints = normalizer._extract_category_hints(
            "iPhone Bluetooth Headphones Case"
        )
        # Could match electronics, audio, accessories
        assert len(hints) >= 2

    def test_normalize_complete_iphone(self, normalizer):
        """Test complete normalization of iPhone title."""
        result = normalizer.normalize(
            "Apple iPhone 15 Pro Max 256GB Space Gray - Brand New Sealed"
        )

        assert result.original_title.startswith("Apple")
        assert result.brand == "Apple"
        assert "storage" in result.attributes
        assert result.attributes["storage"] == "256GB"
        assert "iphone" in result.keywords
        assert "electronics" in result.category_hints
        # Stopwords should be removed
        assert "brand" not in result.normalized_title
        assert "new" not in result.normalized_title
        assert "sealed" not in result.normalized_title

    def test_normalize_complete_laptop(self, normalizer):
        """Test complete normalization of laptop title."""
        result = normalizer.normalize(
            "Dell XPS 15 Laptop 16GB RAM 512GB SSD 15.6 inch"
        )

        assert result.brand == "Dell"
        assert "memory" in result.attributes
        assert result.attributes["memory"] == "16GB"
        assert "storage" in result.attributes
        assert result.attributes["storage"] == "512GB"
        assert "laptop" in result.keywords
        assert "electronics" in result.category_hints

    def test_normalize_generic_product(self, normalizer):
        """Test normalization of generic product without brand."""
        result = normalizer.normalize(
            "Wireless Bluetooth Earbuds TWS Noise Cancelling"
        )

        assert result.brand is None
        assert "wireless" in result.keywords
        assert "bluetooth" in result.keywords
        assert "earbuds" in result.keywords
        assert "audio" in result.category_hints

    def test_normalize_preserves_original(self, normalizer):
        """Test original title is preserved."""
        original = "Apple iPhone 15 Pro - BRAND NEW!"
        result = normalizer.normalize(original)

        assert result.original_title == original
        assert result.original_title != result.normalized_title