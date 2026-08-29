"""Tests for individual policy rules."""
from decimal import Decimal

import pytest

from services.policy.models import (
    EvidenceStrength,
    PolicyRiskCategory,
    PolicyRiskLevel,
)
from services.policy.rules import (
    rule_dropshipping_sourcing,
    rule_eligibility_required,
    rule_hazardous_material,
    rule_ip_authenticity,
    rule_listing_accuracy_condition,
    rule_prohibited_item,
    rule_product_safety,
    rule_restricted_item,
    rule_seller_performance,
    rule_shipping_data_missing,
    rule_shipping_feasibility,
)


def make_listing(**overrides):
    """Create a minimal listing dict."""
    base = {
        "item_id": "v1|001|0",
        "title": "Generic Product",
        "price_value": Decimal("29.99"),
        "price_currency": "USD",
        "marketplace": "EBAY_US",
        "condition": "New",
        "product_brand": None,
        "seller_feedback_percentage": 98.0,
    }
    base.update(overrides)
    return base


def make_supplier(**overrides):
    """Create a minimal supplier dict."""
    base = {
        "product_id": "ali_001",
        "title": "Generic Supplier Product",
        "source": "mock",
        "attributes": {},
        "shipping_options": [
            {"estimated_days_min": 15, "estimated_days_max": 25}
        ],
    }
    base.update(overrides)
    return base


class TestProhibitedItemRule:
    def test_firearm_detected(self):
        listing = make_listing(title="Handgun for Sale")
        finding = rule_prohibited_item(listing, None, "EBAY_US")
        assert finding is not None
        assert finding.category == PolicyRiskCategory.PROHIBITED_ITEM
        assert finding.risk_level == PolicyRiskLevel.HIGH

    def test_cannabis_detected(self):
        listing = make_listing(title="Cannabis Grinder")
        finding = rule_prohibited_item(listing, None, "EBAY_US")
        assert finding is not None

    def test_clean_title_not_flagged(self):
        listing = make_listing(title="Wireless Bluetooth Earbuds")
        finding = rule_prohibited_item(listing, None, "EBAY_US")
        assert finding is None

    def test_empty_title_not_flagged(self):
        listing = make_listing(title="")
        finding = rule_prohibited_item(listing, None, "EBAY_US")
        assert finding is None


class TestRestrictedItemRule:
    def test_alcohol_detected(self):
        listing = make_listing(title="Vintage Wine Bottle")
        finding = rule_restricted_item(listing, None, "EBAY_US")
        assert finding is not None
        assert finding.category == PolicyRiskCategory.RESTRICTED_ITEM
        assert finding.risk_level == PolicyRiskLevel.MEDIUM

    def test_knife_detected(self):
        listing = make_listing(title="Kitchen Knife Set")
        finding = rule_restricted_item(listing, None, "EBAY_US")
        assert finding is not None

    def test_normal_product_not_flagged(self):
        listing = make_listing(title="USB Cable")
        finding = rule_restricted_item(listing, None, "EBAY_US")
        assert finding is None


class TestEligibilityRequiredRule:
    def test_car_seat_detected(self):
        listing = make_listing(title="Baby Car Seat")
        finding = rule_eligibility_required(listing, None, "EBAY_US")
        assert finding is not None
        assert finding.category == PolicyRiskCategory.ELIGIBILITY_REQUIRED

    def test_bike_helmet_detected(self):
        listing = make_listing(title="Bicycle Helmet Adult Size")
        finding = rule_eligibility_required(listing, None, "EBAY_US")
        assert finding is not None

    def test_generic_product_not_flagged(self):
        listing = make_listing(title="USB Adapter")
        finding = rule_eligibility_required(listing, None, "EBAY_US")
        assert finding is None


class TestProductSafetyRule:
    def test_recall_triggers_high(self):
        listing = make_listing(title="Product Recall Notice")
        finding = rule_product_safety(listing, None, "EBAY_US")
        assert finding is not None
        assert finding.risk_level == PolicyRiskLevel.HIGH

    def test_toy_magnet_triggers_review(self):
        listing = make_listing(title="Toy Magnet Set for Kids")
        finding = rule_product_safety(listing, None, "EBAY_US")
        assert finding is not None
        assert finding.risk_level == PolicyRiskLevel.REVIEW_REQUIRED

    def test_normal_product_not_flagged(self):
        listing = make_listing(title="Wireless Charger")
        finding = rule_product_safety(listing, None, "EBAY_US")
        assert finding is None


class TestHazardousMaterialRule:
    def test_lithium_battery_detected(self):
        listing = make_listing(title="Lithium Battery Pack 12V")
        finding = rule_hazardous_material(listing, None, "EBAY_US")
        assert finding is not None
        assert finding.category == PolicyRiskCategory.HAZARDOUS_MATERIAL
        assert finding.risk_level == PolicyRiskLevel.REVIEW_REQUIRED

    def test_flammable_detected(self):
        listing = make_listing(title="Flammable Liquid Container")
        finding = rule_hazardous_material(listing, None, "EBAY_US")
        assert finding is not None

    def test_normal_product_not_flagged(self):
        listing = make_listing(title="Wooden Cutting Board")
        finding = rule_hazardous_material(listing, None, "EBAY_US")
        assert finding is None


class TestIPAuthenticityRule:
    def test_replica_language_detected(self):
        listing = make_listing(title="Apple Watch Replica Style")
        finding = rule_ip_authenticity(listing, None, "EBAY_US")
        assert finding is not None
        assert finding.risk_level == PolicyRiskLevel.HIGH

    def test_branded_with_mock_supplier(self):
        listing = make_listing(
            title="Apple iPhone 15 Pro Max Case",
            product_brand="Apple",
        )
        supplier = make_supplier(source="mock")
        finding = rule_ip_authenticity(listing, supplier, "EBAY_US")
        assert finding is not None
        assert finding.risk_level == PolicyRiskLevel.REVIEW_REQUIRED

    def test_branded_without_supplier_still_flagged(self):
        listing = make_listing(
            title="Nike Air Max Running Shoes",
            product_brand="Nike",
        )
        finding = rule_ip_authenticity(listing, None, "EBAY_US")
        assert finding is not None
        assert finding.risk_level == PolicyRiskLevel.REVIEW_REQUIRED

    def test_generic_product_not_flagged(self):
        listing = make_listing(title="Wireless Earbuds Bluetooth")
        finding = rule_ip_authenticity(listing, None, "EBAY_US")
        assert finding is None


class TestShippingFeasibilityRule:
    def test_slow_shipping_medium_risk(self):
        listing = make_listing()
        supplier = make_supplier(
            shipping_options=[
                {"estimated_days_min": 30, "estimated_days_max": 45}
            ]
        )
        finding = rule_shipping_feasibility(listing, supplier, "EBAY_US")
        assert finding is not None
        assert finding.risk_level == PolicyRiskLevel.MEDIUM

    def test_moderate_shipping_review(self):
        listing = make_listing()
        supplier = make_supplier(
            shipping_options=[
                {"estimated_days_min": 15, "estimated_days_max": 25}
            ]
        )
        finding = rule_shipping_feasibility(listing, supplier, "EBAY_US")
        assert finding is not None
        assert finding.risk_level == PolicyRiskLevel.REVIEW_REQUIRED

    def test_fast_shipping_no_finding(self):
        listing = make_listing()
        supplier = make_supplier(
            shipping_options=[
                {"estimated_days_min": 3, "estimated_days_max": 7}
            ]
        )
        finding = rule_shipping_feasibility(listing, supplier, "EBAY_US")
        assert finding is None

    def test_no_supplier_no_finding(self):
        listing = make_listing()
        finding = rule_shipping_feasibility(listing, None, "EBAY_US")
        assert finding is None


class TestShippingDataMissingRule:
    def test_missing_shipping_data_flagged(self):
        listing = make_listing()
        supplier = make_supplier(shipping_options=[])
        finding = rule_shipping_data_missing(listing, supplier, "EBAY_US")
        assert finding is not None
        assert finding.risk_level == PolicyRiskLevel.REVIEW_REQUIRED

    def test_present_shipping_data_no_finding(self):
        listing = make_listing()
        supplier = make_supplier()  # has default shipping
        finding = rule_shipping_data_missing(listing, supplier, "EBAY_US")
        assert finding is None

    def test_no_supplier_no_finding(self):
        listing = make_listing()
        finding = rule_shipping_data_missing(listing, None, "EBAY_US")
        assert finding is None


class TestDropshippingRule:
    def test_aliexpress_mock_supplier_flagged(self):
        listing = make_listing()
        supplier = make_supplier(source="mock")
        finding = rule_dropshipping_sourcing(listing, supplier, "EBAY_US")
        assert finding is not None
        assert finding.category == PolicyRiskCategory.DROPSHIPPING
        assert finding.risk_level == PolicyRiskLevel.MEDIUM

    def test_no_supplier_no_finding(self):
        listing = make_listing()
        finding = rule_dropshipping_sourcing(listing, None, "EBAY_US")
        assert finding is None


class TestListingAccuracyRule:
    def test_new_vs_used_mismatch(self):
        listing = make_listing(condition="New")
        supplier = make_supplier(
            attributes={"condition": "used refurbished"}
        )
        finding = rule_listing_accuracy_condition(
            listing, supplier, "EBAY_US"
        )
        assert finding is not None
        assert finding.category == PolicyRiskCategory.LISTING_ACCURACY

    def test_matching_conditions_no_finding(self):
        listing = make_listing(condition="New")
        supplier = make_supplier(attributes={"condition": "brand new"})
        finding = rule_listing_accuracy_condition(
            listing, supplier, "EBAY_US"
        )
        assert finding is None

    def test_no_supplier_no_finding(self):
        listing = make_listing()
        finding = rule_listing_accuracy_condition(
            listing, None, "EBAY_US"
        )
        assert finding is None


class TestSellerPerformanceRule:
    def test_low_feedback_high_risk(self):
        data = {"seller_feedback_percentage": 85.0}
        finding = rule_seller_performance(data, "EBAY_US")
        assert finding is not None
        assert finding.risk_level == PolicyRiskLevel.HIGH

    def test_medium_feedback_medium_risk(self):
        data = {"seller_feedback_percentage": 93.0}
        finding = rule_seller_performance(data, "EBAY_US")
        assert finding is not None
        assert finding.risk_level == PolicyRiskLevel.MEDIUM

    def test_high_feedback_no_finding(self):
        data = {"seller_feedback_percentage": 99.5}
        finding = rule_seller_performance(data, "EBAY_US")
        assert finding is None

    def test_missing_feedback_no_finding(self):
        data = {}
        finding = rule_seller_performance(data, "EBAY_US")
        assert finding is None

    def test_invalid_feedback_no_finding(self):
        data = {"seller_feedback_percentage": "not a number"}
        finding = rule_seller_performance(data, "EBAY_US")
        assert finding is None