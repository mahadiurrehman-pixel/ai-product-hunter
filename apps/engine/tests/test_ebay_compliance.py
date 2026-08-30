"""
Tests for eBay Marketplace Account Deletion compliance.

Covers challenge verification, signature verification,
nested payload parsing, user data purge, and edge cases.
"""
import hashlib
import hmac
import json
import pytest

from services.ebay.compliance import (
    ComplianceConfig,
    ComplianceStatus,
    EbayComplianceHandler,
    NotificationResult,
)


@pytest.fixture
def config():
    return ComplianceConfig(
        verification_token="test_verification_token_abc123",
        endpoint_url="https://rehu.example.com/ebay/notifications",
        environment="sandbox",
    )


@pytest.fixture
def handler(config):
    return EbayComplianceHandler(config=config)


# ==================================================================
# Configuration Tests
# ==================================================================

class TestComplianceConfig:
    def test_configured_status(self, config):
        assert config.is_configured is True
        assert config.status == ComplianceStatus.IMPLEMENTED

    def test_unconfigured_status(self):
        config = ComplianceConfig(
            verification_token="", endpoint_url=""
        )
        assert config.is_configured is False
        assert config.status == ComplianceStatus.NOT_CONFIGURED

    def test_partial_config_not_configured(self):
        config = ComplianceConfig(
            verification_token="token", endpoint_url=""
        )
        assert config.is_configured is False


# ==================================================================
# Challenge Verification Tests
# ==================================================================

class TestChallengeVerification:
    def test_valid_challenge(self, handler, config):
        challenge_code = "test_challenge_xyz789"
        result = handler.handle_challenge(
            {"challenge_code": challenge_code}
        )

        raw = (
            challenge_code
            + config.verification_token
            + config.endpoint_url
        )
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        # eBay spec uses camelCase: challengeResponse
        assert "challengeResponse" in result
        assert result["challengeResponse"] == expected

    def test_challenge_deterministic(self, handler):
        params = {"challenge_code": "deterministic_test"}
        r1 = handler.handle_challenge(params)
        r2 = handler.handle_challenge(params)
        assert r1["challengeResponse"] == r2["challengeResponse"]

    def test_different_challenges_different_hashes(self, handler):
        r1 = handler.handle_challenge({"challenge_code": "aaa"})
        r2 = handler.handle_challenge({"challenge_code": "bbb"})
        assert r1["challengeResponse"] != r2["challengeResponse"]

    def test_missing_challenge_code_raises(self, handler):
        with pytest.raises(ValueError, match="Missing challenge_code"):
            handler.handle_challenge({})

    def test_empty_challenge_code_raises(self, handler):
        with pytest.raises(ValueError, match="Missing challenge_code"):
            handler.handle_challenge({"challenge_code": ""})

    def test_unconfigured_handler_raises(self):
        handler = EbayComplianceHandler(
            config=ComplianceConfig(
                verification_token="", endpoint_url=""
            )
        )
        with pytest.raises(ValueError, match="not configured"):
            handler.handle_challenge({"challenge_code": "test"})


# ==================================================================
# Signature Verification Tests
# ==================================================================

class TestSignatureVerification:
    def test_valid_signature(self, handler, config):
        raw_body = b'{"metadata":{"topic":"TEST"}}'
        expected_sig = hmac.new(
            key=config.verification_token.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        assert handler.verify_signature(raw_body, expected_sig) is True

    def test_invalid_signature(self, handler):
        raw_body = b'{"metadata":{"topic":"TEST"}}'
        assert handler.verify_signature(raw_body, "invalid_sig") is False

    def test_empty_signature(self, handler):
        raw_body = b'{"test": true}'
        assert handler.verify_signature(raw_body, "") is False

    def test_tampered_body_fails(self, handler, config):
        original_body = b'{"userId": "123"}'
        tampered_body = b'{"userId": "456"}'

        sig = hmac.new(
            key=config.verification_token.encode("utf-8"),
            msg=original_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        assert handler.verify_signature(original_body, sig) is True
        assert handler.verify_signature(tampered_body, sig) is False

    def test_unconfigured_token_fails(self):
        handler = EbayComplianceHandler(
            config=ComplianceConfig(
                verification_token="", endpoint_url=""
            )
        )
        assert handler.verify_signature(b"body", "sig") is False


# ==================================================================
# Notification Handling Tests
# ==================================================================

class TestNotificationHandling:
    def test_valid_notification_nested_payload(self, handler):
        payload = {
            "metadata": {
                "topic": "MARKETPLACE_ACCOUNT_DELETION",
                "notificationId": "notif_nested_001",
            },
            "notification": {
                "notificationId": "notif_nested_001",
                "eventDate": "2024-03-29T09:55:00.000Z",
                "data": {
                    "username": "test_seller",
                    "userId": "987654321",
                    "eiasToken": "NY+abc123",
                },
            },
        }
        result = handler.handle_notification(payload)
        assert isinstance(result, NotificationResult)
        assert result.success is True
        assert "notif_nested_001" in result.message

    def test_valid_notification_top_level_fallback(self, handler):
        payload = {
            "metadata": {
                "topic": "MARKETPLACE_ACCOUNT_DELETION",
                "notificationId": "notif_toplevel_001",
            },
            "userId": "111222333",
            "username": "old_format_user",
        }
        result = handler.handle_notification(payload)
        assert result.success is True

    def test_missing_topic(self, handler):
        payload = {
            "metadata": {"notificationId": "notif_002"},
            "notification": {"data": {"userId": "99"}},
        }
        result = handler.handle_notification(payload)
        assert result.success is False
        assert "topic" in result.message.lower()

    def test_empty_payload(self, handler):
        result = handler.handle_notification({})
        assert result.success is False

    def test_unconfigured_handler(self):
        handler = EbayComplianceHandler(
            config=ComplianceConfig(
                verification_token="", endpoint_url=""
            )
        )
        result = handler.handle_notification({
            "metadata": {"topic": "TEST", "notificationId": "x"},
        })
        assert result.success is False
        assert "not configured" in result.message.lower()

    def test_notification_idempotency(self, handler):
        payload = {
            "metadata": {
                "topic": "MARKETPLACE_ACCOUNT_DELETION",
                "notificationId": "dup_001",
            },
            "notification": {
                "data": {"userId": "dup_user", "username": "dup"},
            },
        }
        r1 = handler.handle_notification(payload)
        r2 = handler.handle_notification(payload)
        assert r1.success is True
        assert r2.success is True

    def test_notification_timestamp(self, handler):
        payload = {
            "metadata": {
                "topic": "MARKETPLACE_ACCOUNT_DELETION",
                "notificationId": "ts_001",
            },
            "notification": {"data": {"userId": "ts"}},
        }
        result = handler.handle_notification(payload)
        assert result.timestamp
        assert "T" in result.timestamp

    def test_signature_rejects_invalid(self, handler, config):
        payload = {
            "metadata": {
                "topic": "MARKETPLACE_ACCOUNT_DELETION",
                "notificationId": "sig_test_001",
            },
            "notification": {"data": {"userId": "123"}},
        }
        raw_body = json.dumps(payload).encode("utf-8")

        result = handler.handle_notification(
            payload=payload,
            raw_body=raw_body,
            signature_header="invalid_signature",
        )
        assert result.success is False
        assert "signature" in result.message.lower()

    def test_signature_accepts_valid(self, handler, config):
        payload = {
            "metadata": {
                "topic": "MARKETPLACE_ACCOUNT_DELETION",
                "notificationId": "sig_valid_001",
            },
            "notification": {"data": {"userId": "456"}},
        }
        raw_body = json.dumps(payload).encode("utf-8")
        valid_sig = hmac.new(
            key=config.verification_token.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        result = handler.handle_notification(
            payload=payload,
            raw_body=raw_body,
            signature_header=valid_sig,
        )
        assert result.success is True


# ==================================================================
# Compliance Status Tests
# ==================================================================

class TestComplianceStatus:
    def test_all_statuses_exist(self):
        assert ComplianceStatus.NOT_CONFIGURED.value == "not_configured"
        assert ComplianceStatus.IMPLEMENTED.value == "implemented"
        assert ComplianceStatus.READY_FOR_DEPLOYMENT.value == "ready_for_deployment"
        assert ComplianceStatus.AWAITING_EBAY_VERIFICATION.value == "awaiting_ebay_verification"
        assert ComplianceStatus.VERIFIED.value == "verified"
        assert ComplianceStatus.PRODUCTION_ENABLED.value == "production_enabled"