"""Tests for PolicyChecker orchestrator."""
from decimal import Decimal

import pytest

from services.ebay.marketplace import EbayMarketplace
from services.policy import (
    PolicyAssessment,
    PolicyChecker,
    PolicyRiskCategory,
    PolicyRiskLevel,
)


class TestPolicyCheckerBasics:
    @pytest.fixture
    def checker(self):
        return PolicyChecker()

    def test_check_returns_assessment(self, checker):
        listing = {
            "item_id": "v1|001|0",
            "title": "Wireless Earbuds",
            "price_value": Decimal("29.99"),
            "price_currency": "USD",
        }
        result = checker.check(listing)
        assert isinstance(result, PolicyAssessment)

    def test_empty_listing_returns_review_required(self, checker):
        result = checker.check({})
        assert result.overall_risk == PolicyRiskLevel.REVIEW_REQUIRED

    def test_none_listing_returns_review_required(self, checker):
        result = checker.check(None)
        assert result.overall_risk == PolicyRiskLevel.REVIEW_REQUIRED

    def test_clean_product_is_low_risk(self, checker):
        listing = {
            "item_id": "v1|001|0",
            "title": "Wireless Bluetooth Earbuds",
            "price_value": Decimal("29.99"),
            "condition": "New",
        }
        result = checker.check(listing)
        assert result.overall_risk == PolicyRiskLevel.LOW
        assert len(result.findings) == 0

    def test_prohibited_product_is_high_risk(self, checker):
        listing = {
            "item_id": "v1|001|0",
            "title": "Handgun For Sale",
            "price_value": Decimal("500.00"),
        }
        result = checker.check(listing)
        assert result.overall_risk == PolicyRiskLevel.HIGH

    def test_restricted_product_is_medium_risk(self, checker):
        listing = {
            "item_id": "v1|001|0",
            "title": "Kitchen Knife Set",
            "price_value": Decimal("50.00"),
        }
        result = checker.check(listing)
        assert result.overall_risk == PolicyRiskLevel.MEDIUM


class TestPolicyCheckerMarketplaces:
    @pytest.fixture
    def checker(self):
        return PolicyChecker()

    @pytest.fixture
    def base_listing(self):
        return {
            "item_id": "v1|001|0",
            "title": "Wireless Earbuds",
            "price_value": Decimal("29.99"),
            "condition": "New",
        }

    def test_us_marketplace(self, checker, base_listing):
        result = checker.check(base_listing, marketplace=EbayMarketplace.US)
        assert result.marketplace == "EBAY_US"

    def test_uk_marketplace(self, checker, base_listing):
        result = checker.check(base_listing, marketplace=EbayMarketplace.UK)
        assert result.marketplace == "EBAY_GB"

    def test_germany_marketplace(self, checker, base_listing):
        result = checker.check(
            base_listing, marketplace=EbayMarketplace.GERMANY
        )
        assert result.marketplace == "EBAY_DE"

    def test_australia_marketplace(self, checker, base_listing):
        result = checker.check(
            base_listing, marketplace=EbayMarketplace.AUSTRALIA
        )
        assert result.marketplace == "EBAY_AU"

    def test_canada_marketplace(self, checker, base_listing):
        result = checker.check(
            base_listing, marketplace=EbayMarketplace.CANADA
        )
        assert result.marketplace == "EBAY_CA"

    def test_string_marketplace_accepted(self, checker, base_listing):
        result = checker.check(base_listing, marketplace="EBAY_GB")
        assert result.marketplace == "EBAY_GB"

    def test_invalid_marketplace_defaults_us(self, checker, base_listing):
        result = checker.check(base_listing, marketplace="EBAY_JP")
        assert result.marketplace == "EBAY_US"


class TestPolicyCheckerWithSupplier:
    @pytest.fixture
    def checker(self):
        return PolicyChecker()

    def test_supplier_context_enables_dropshipping_finding(self, checker):
        listing = {
            "item_id": "v1|001|0",
            "title": "Wireless Earbuds",
            "price_value": Decimal("29.99"),
        }
        supplier = {
            "product_id": "ali_001",
            "source": "mock",
            "shipping_options": [
                {"estimated_days_min": 10, "estimated_days_max": 20}
            ],
        }
        result = checker.check(
            listing, marketplace=EbayMarketplace.US, supplier=supplier
        )
        # Should detect dropshipping concern
        categories = {f.category for f in result.findings}
        assert PolicyRiskCategory.DROPSHIPPING in categories

    def test_no_supplier_no_dropshipping_finding(self, checker):
        listing = {
            "item_id": "v1|001|0",
            "title": "Wireless Earbuds",
            "price_value": Decimal("29.99"),
        }
        result = checker.check(listing)
        categories = {f.category for f in result.findings}
        assert PolicyRiskCategory.DROPSHIPPING not in categories

    def test_slow_supplier_shipping_medium_risk(self, checker):
        listing = {
            "item_id": "v1|001|0",
            "title": "Wireless Earbuds",
            "price_value": Decimal("29.99"),
        }
        supplier = {
            "product_id": "ali_001",
            "source": "mock",
            "shipping_options": [
                {"estimated_days_min": 35, "estimated_days_max": 45}
            ],
        }
        result = checker.check(
            listing, marketplace=EbayMarketplace.US, supplier=supplier
        )
        shipping_findings = [
            f for f in result.findings
            if f.category == PolicyRiskCategory.SHIPPING
        ]
        assert len(shipping_findings) > 0

    def test_branded_with_mock_supplier_ip_review(self, checker):
        listing = {
            "item_id": "v1|001|0",
            "title": "Apple iPhone Case",
            "price_value": Decimal("9.99"),
            "product_brand": "Apple",
        }
        supplier = {
            "product_id": "ali_001",
            "source": "mock",
            "shipping_options": [
                {"estimated_days_min": 10, "estimated_days_max": 20}
            ],
        }
        result = checker.check(
            listing, marketplace=EbayMarketplace.US, supplier=supplier
        )
        ip_findings = [
            f for f in result.findings
            if f.category == PolicyRiskCategory.IP_AUTHENTICITY
        ]
        assert len(ip_findings) > 0


class TestPolicyCheckerSellerCheck:
    @pytest.fixture
    def checker(self):
        return PolicyChecker()

    def test_check_seller_high_feedback_low_risk(self, checker):
        seller = {
            "seller_username": "great_seller",
            "seller_feedback_percentage": 99.5,
        }
        result = checker.check_seller(seller)
        assert result.overall_risk == PolicyRiskLevel.LOW

    def test_check_seller_low_feedback_high_risk(self, checker):
        seller = {
            "seller_username": "problem_seller",
            "seller_feedback_percentage": 82.0,
        }
        result = checker.check_seller(seller)
        assert result.overall_risk == PolicyRiskLevel.HIGH

    def test_check_seller_medium_feedback(self, checker):
        seller = {
            "seller_username": "avg_seller",
            "seller_feedback_percentage": 92.0,
        }
        result = checker.check_seller(seller)
        assert result.overall_risk == PolicyRiskLevel.MEDIUM


class TestPolicyCheckerOutput:
    @pytest.fixture
    def checker(self):
        return PolicyChecker()

    def test_output_has_disclaimer(self, checker):
        listing = {"item_id": "v1|1|0", "title": "Test", "price_value": Decimal("10")}
        result = checker.check(listing)
        d = result.to_dict()
        assert "disclaimer" in d
        assert len(d["disclaimer"]) > 0

    def test_output_has_limitations(self, checker):
        listing = {"item_id": "v1|1|0", "title": "Test", "price_value": Decimal("10")}
        result = checker.check(listing)
        d = result.to_dict()
        assert "limitations" in d
        assert len(d["limitations"]) > 0

    def test_output_has_policy_version(self, checker):
        listing = {"item_id": "v1|1|0", "title": "Test", "price_value": Decimal("10")}
        result = checker.check(listing)
        d = result.to_dict()
        assert d["policy_version"] == "mvp-baseline-2025"

    def test_findings_have_source(self, checker):
        listing = {
            "item_id": "v1|1|0",
            "title": "Handgun",  # triggers prohibited
            "price_value": Decimal("500"),
        }
        result = checker.check(listing)
        for f in result.findings:
            assert f.source is not None
            assert f.source.url != ""
            assert f.source.name != ""

    def test_findings_have_rule_id(self, checker):
        listing = {
            "item_id": "v1|1|0",
            "title": "Cannabis Product",
            "price_value": Decimal("10"),
        }
        result = checker.check(listing)
        for f in result.findings:
            assert f.rule_id != ""

    def test_serializable_to_dict(self, checker):
        listing = {
            "item_id": "v1|1|0",
            "title": "Vintage Wine Bottle",
            "price_value": Decimal("50"),
        }
        result = checker.check(listing)
        d = result.to_dict()
        # Must be JSON-serializable-friendly
        import json
        json.dumps(d, default=str)  # should not raise