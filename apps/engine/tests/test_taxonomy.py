"""Tests for Canonical Product Taxonomy."""
import pytest
from services.product_identity import (
    TaxonomyEngine, ProductTypeInfo, ProductIdentityBuilder,
)


@pytest.fixture
def taxonomy():
    return TaxonomyEngine()

@pytest.fixture
def builder():
    return ProductIdentityBuilder()


class TestTaxonomyLoading:
    def test_types_loaded(self, taxonomy):
        assert len(taxonomy.all_types()) > 20

    def test_aliases_loaded(self, taxonomy):
        info = taxonomy.resolve_type("iPhone 15")
        assert info is not None
        assert info.name == "smartphone"

    def test_get_type(self, taxonomy):
        info = taxonomy.get_type("phone_case")
        assert info is not None
        assert info.role == "accessory"

    def test_unknown_type(self, taxonomy):
        info = taxonomy.get_type("nonexistent_type")
        assert info is None


class TestDeviceTypes:
    def test_smartphone(self, taxonomy):
        info = taxonomy.resolve_type("Apple iPhone 15 Pro Max")
        assert info.name == "smartphone"
        assert info.role == "device"

    def test_laptop(self, taxonomy):
        info = taxonomy.resolve_type("Dell XPS 15 Laptop")
        assert info.name == "laptop"
        assert info.role == "device"

    def test_headphones(self, taxonomy):
        info = taxonomy.resolve_type("Sony WH-1000XM5 Headphones")
        assert info.name == "headphones"
        assert info.role == "device"

    def test_earbuds(self, taxonomy):
        info = taxonomy.resolve_type("Wireless Bluetooth Earbuds TWS")
        assert info.name == "earbuds"
        assert info.role == "device"

    def test_speaker(self, taxonomy):
        info = taxonomy.resolve_type("Bluetooth Speaker Portable")
        assert info.name == "speaker"
        assert info.role == "device"

    def test_tablet(self, taxonomy):
        info = taxonomy.resolve_type("iPad Pro 12.9 inch")
        assert info.name == "tablet"

    def test_camera(self, taxonomy):
        info = taxonomy.resolve_type("Canon DSLR Camera")
        assert info.name == "camera"


class TestAccessoryTypes:
    def test_phone_case(self, taxonomy):
        info = taxonomy.resolve_type("iPhone 15 Case Silicone")
        assert info.name == "phone_case"
        assert info.role == "accessory"
        assert "smartphone" in info.compatible_categories

    def test_screen_protector(self, taxonomy):
        info = taxonomy.resolve_type("Samsung Galaxy S24 Screen Protector")
        assert info.name == "screen_protector"
        assert info.role == "accessory"

    def test_charger(self, taxonomy):
        info = taxonomy.resolve_type("USB-C Fast Charger 20W")
        assert info.name == "charger"
        assert info.role == "accessory"

    def test_charging_cable(self, taxonomy):
        info = taxonomy.resolve_type("USB-C to Lightning Cable")
        assert info.name == "charging_cable"
        assert info.role == "accessory"

    def test_laptop_stand(self, taxonomy):
        info = taxonomy.resolve_type("MacBook Laptop Stand")
        assert info.name == "laptop_stand"
        assert "laptop" in info.compatible_categories


class TestReplacementParts:
    def test_replacement_battery(self, taxonomy):
        info = taxonomy.resolve_type("iPhone Replacement Battery")
        assert info.name == "replacement_battery"
        assert info.role == "replacement_part"

    def test_ear_tips(self, taxonomy):
        info = taxonomy.resolve_type("AirPods Replacement Ear Tips")
        assert info.name == "ear_tips"
        assert info.role == "replacement_part"


class TestPriority:
    def test_case_wins_over_phone(self, taxonomy):
        """'iPhone 15 Case' → phone_case, NOT smartphone."""
        info = taxonomy.resolve_type("iPhone 15 Pro Max Case")
        assert info.name == "phone_case"
        assert info.name != "smartphone"

    def test_protector_wins_over_phone(self, taxonomy):
        info = taxonomy.resolve_type("Samsung Galaxy S24 Screen Protector")
        assert info.name == "screen_protector"

    def test_ear_tips_wins_over_earbuds(self, taxonomy):
        info = taxonomy.resolve_type("AirPods Pro Replacement Ear Tips")
        assert info.name == "ear_tips"
        assert info.name != "earbuds"

    def test_charger_wins_over_generic(self, taxonomy):
        info = taxonomy.resolve_type("iPhone Fast Charger USB-C")
        assert info.name == "charger"


class TestCategoryPath:
    def test_device_path(self, taxonomy):
        path = taxonomy.get_category_path("smartphone")
        assert "electronics" in path
        assert "devices" in path
        assert "smartphone" in path

    def test_accessory_path(self, taxonomy):
        path = taxonomy.get_category_path("phone_case")
        assert "electronics" in path
        assert "accessories" in path
        assert "phone_case" in path


class TestRoles:
    def test_device_role(self, taxonomy):
        assert taxonomy.get_role("smartphone") == "device"
        assert taxonomy.get_role("laptop") == "device"

    def test_accessory_role(self, taxonomy):
        assert taxonomy.get_role("phone_case") == "accessory"
        assert taxonomy.get_role("charger") == "accessory"

    def test_replacement_role(self, taxonomy):
        assert taxonomy.get_role("replacement_battery") == "replacement_part"
        assert taxonomy.get_role("ear_tips") == "replacement_part"

    def test_component_role(self, taxonomy):
        assert taxonomy.get_role("adapter") == "component"
        assert taxonomy.get_role("ssd") == "component"

    def test_types_by_role(self, taxonomy):
        devices = taxonomy.types_by_role("device")
        assert "smartphone" in devices
        assert "laptop" in devices
        assert "phone_case" not in devices


class TestProductIdentityIntegration:
    def test_role_populated(self, builder):
        identity = builder.from_title("Apple iPhone 15 Pro Max")
        assert identity.product_role == "device"

    def test_accessory_role(self, builder):
        identity = builder.from_title("iPhone 15 Case Silicone")
        assert identity.product_role == "accessory"
        assert identity.is_accessory is True

    def test_category_path_populated(self, builder):
        identity = builder.from_title("Apple iPhone 15 Pro Max")
        assert len(identity.category_path) > 0
        assert "electronics" in identity.category_path

    def test_compatible_categories(self, builder):
        identity = builder.from_title("iPhone 15 Case")
        assert "smartphone" in identity.compatible_categories

    def test_device_no_compatible_categories(self, builder):
        identity = builder.from_title("Apple iPhone 15")
        assert identity.compatible_categories == []

    def test_to_dict_includes_taxonomy(self, builder):
        identity = builder.from_title("iPhone 15 Case")
        d = identity.to_dict()
        assert "product_role" in d
        assert "category_path" in d
        assert "compatible_categories" in d

    def test_replacement_part_role(self, builder):
        identity = builder.from_title("iPhone Replacement Battery")
        assert identity.product_role == "replacement_part"

    def test_backward_compat_is_accessory(self, builder):
        identity = builder.from_title("iPhone 15 Case")
        assert identity.is_accessory is True
        assert identity.product_type == "phone_case"
        assert identity.product_role == "accessory"


class TestAliases:
    def test_mobile_phone_alias(self, taxonomy):
        info = taxonomy.resolve_type("Mobile Phone Samsung")
        assert info.name == "smartphone"

    def test_cell_phone_alias(self, taxonomy):
        info = taxonomy.resolve_type("Cell Phone Case")
        assert info.name == "phone_case"

    def test_tempered_glass_alias(self, taxonomy):
        info = taxonomy.resolve_type("Tempered Glass Samsung S24")
        assert info.name == "screen_protector"

    def test_notebook_alias(self, taxonomy):
        info = taxonomy.resolve_type("Dell Notebook 15 inch")
        assert info.name == "laptop"


class TestUnknownType:
    def test_ambiguous_product(self, taxonomy):
        info = taxonomy.resolve_type("Premium Quality Item")
        assert info is None

    def test_generic_title(self, builder):
        identity = builder.from_title("New Hot Sale Best Deal")
        assert identity.product_role == "unknown"


class TestDeterminism:
    def test_same_input_same_output(self, builder):
        title = "Apple iPhone 15 Pro Max 256GB Case"
        r1 = builder.from_title(title).to_dict()
        r2 = builder.from_title(title).to_dict()
        assert r1 == r2