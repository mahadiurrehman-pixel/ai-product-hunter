"""
eBay Marketplace Account Deletion/Closure Compliance.

Implements the notification endpoint required by eBay's Developer Program
for Production keyset activation.

eBay Documentation Reference:
https://developer.ebay.com/api-docs/commerce/notification/overview.html
https://developer.ebay.com/marketplace-account-deletion

Status: IMPLEMENTED — AWAITING DEPLOYMENT & EBAY VERIFICATION
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import get_logger

logger = get_logger(__name__)


class ComplianceStatus(str, Enum):
    """eBay Production compliance lifecycle states."""
    NOT_CONFIGURED = "not_configured"
    IMPLEMENTED = "implemented"
    READY_FOR_DEPLOYMENT = "ready_for_deployment"
    AWAITING_EBAY_VERIFICATION = "awaiting_ebay_verification"
    VERIFIED = "verified"
    PRODUCTION_ENABLED = "production_enabled"


@dataclass
class ComplianceConfig:
    """
    Configuration for eBay compliance endpoint.

    All values must come from environment variables.
    Never hardcode verification tokens or secrets.
    """
    verification_token: str
    endpoint_url: str
    environment: str = "sandbox"

    @classmethod
    def from_settings(cls) -> "ComplianceConfig":
        """Load from application settings / environment."""
        try:
            from config import settings
            return cls(
                verification_token=getattr(
                    settings, "ebay_verification_token", ""
                ),
                endpoint_url=getattr(
                    settings, "ebay_notification_endpoint_url", ""
                ),
                environment=getattr(
                    settings, "ebay_environment", "sandbox"
                ),
            )
        except Exception:
            return cls(
                verification_token="",
                endpoint_url="",
                environment="sandbox",
            )

    @property
    def is_configured(self) -> bool:
        return bool(self.verification_token and self.endpoint_url)

    @property
    def status(self) -> ComplianceStatus:
        if not self.is_configured:
            return ComplianceStatus.NOT_CONFIGURED
        return ComplianceStatus.IMPLEMENTED


@dataclass
class ChallengeResponse:
    """Response to eBay's challenge verification request."""
    challenge_response: str


@dataclass
class NotificationResult:
    """Result of processing an account deletion notification."""
    success: bool
    message: str
    timestamp: str = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    records_purged: int = 0


class EbayComplianceHandler:
    """
    Handles eBay Marketplace Account Deletion/Closure notifications.

    Responsibilities:
    1. Verify X-EBAY-SIGNATURE header (HMAC-SHA256)
    2. Respond to eBay's challenge verification (GET request)
    3. Process account deletion notifications (POST request)
    4. Purge user-linked data from REHU database
    5. Log all interactions for audit (PII redacted)
    """

    def __init__(self, config: Optional[ComplianceConfig] = None):
        self._config = config or ComplianceConfig.from_settings()

    @property
    def config(self) -> ComplianceConfig:
        return self._config

    # ------------------------------------------------------------------
    # Change 1: Signature Verification (HMAC-SHA256)
    # ------------------------------------------------------------------

    def verify_signature(
        self, raw_body: bytes, signature_header: str
    ) -> bool:
        """
        Verify the X-EBAY-SIGNATURE header against the raw request body.

        eBay signs notifications using:
            HMAC-SHA256(key=verification_token, message=raw_body)

        Args:
            raw_body: The raw, unmodified HTTP request body bytes.
            signature_header: The value of the X-EBAY-SIGNATURE header.

        Returns:
            True if signature is valid, False otherwise.
        """
        if not self._config.verification_token:
            logger.error(
                "Cannot verify signature: verification_token not configured"
            )
            return False

        if not signature_header:
            logger.warning("Missing X-EBAY-SIGNATURE header")
            return False

        expected = hmac.new(
            key=self._config.verification_token.encode("utf-8"),
            msg=raw_body,
            digestmod=hashlib.sha256,
        ).hexdigest()

        # Constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(expected, signature_header)

        if not is_valid:
            logger.warning("X-EBAY-SIGNATURE verification failed")

        return is_valid

    # ------------------------------------------------------------------
    # Challenge Verification (GET)
    # ------------------------------------------------------------------

    def handle_challenge(
        self, query_params: Dict[str, str]
    ) -> Dict[str, str]:
        """
        Handle eBay's challenge verification request.

        eBay sends a GET request with a `challenge_code` query parameter.
        The endpoint must:
        1. Extract the challenge_code
        2. Concatenate: challenge_code + verification_token + endpoint_url
        3. SHA-256 hash the concatenated string
        4. Return the hash as `challenge_response` in JSON

        Args:
            query_params: URL query parameters from eBay's GET request

        Returns:
            Dict with `challenge_response` key containing the SHA-256 hash

        Raises:
            ValueError: If challenge_code is missing or config is incomplete
        """
        if not self._config.is_configured:
            logger.error(
                "Compliance endpoint not configured. "
                "Set EBAY_VERIFICATION_TOKEN and EBAY_NOTIFICATION_ENDPOINT_URL."
            )
            raise ValueError("Compliance endpoint not configured")

        challenge_code = query_params.get("challenge_code", "")
        if not challenge_code:
            logger.warning("Challenge request missing challenge_code parameter")
            raise ValueError("Missing challenge_code parameter")

        # eBay specification: SHA256(challenge_code + verification_token + endpoint_url)
        raw = (
            challenge_code
            + self._config.verification_token
            + self._config.endpoint_url
        )
        response_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        logger.info("eBay challenge verification processed successfully")

        return {"challengeResponse": response_hash}

    # ------------------------------------------------------------------
    # Change 2: Fix Nested Payload Parsing
    # ------------------------------------------------------------------

    def handle_notification(
        self,
        payload: Dict[str, Any],
        raw_body: Optional[bytes] = None,
        signature_header: Optional[str] = None,
    ) -> NotificationResult:
        """
        Process an eBay Marketplace Account Deletion notification.

        Args:
            payload: Parsed JSON body from eBay's POST notification.
            raw_body: Raw request body bytes for signature verification.
            signature_header: X-EBAY-SIGNATURE header value.

        Returns:
            NotificationResult indicating success or failure.
        """
        if not self._config.is_configured:
            logger.error("Compliance endpoint not configured")
            return NotificationResult(
                success=False,
                message="Endpoint not configured",
            )

        # Step 1: Verify signature if raw_body and header provided
        if raw_body is not None and signature_header is not None:
            if not self.verify_signature(raw_body, signature_header):
                logger.warning(
                    "Notification rejected: invalid X-EBAY-SIGNATURE"
                )
                return NotificationResult(
                    success=False,
                    message="Invalid signature",
                )

        # Step 2: Extract metadata
        metadata = payload.get("metadata", {})
        notification_type = metadata.get("topic", "")
        notification_id = metadata.get("notificationId", "")

        if not notification_type:
            logger.warning(
                f"Malformed notification: missing topic. "
                f"Payload keys: {list(payload.keys())}"
            )
            return NotificationResult(
                success=False,
                message="Missing notification topic",
            )

        # Step 3: Extract user data from correct nested path
        # eBay schema: payload["notification"]["data"]["userId"]
        # Fallback: top-level for backward compatibility
        notification_block = payload.get("notification", {})
        data_block = notification_block.get("data", {})

        user_id = (
            data_block.get("userId")
            or notification_block.get("userId")
            or payload.get("userId")
            or "unknown"
        )
        username = (
            data_block.get("username")
            or notification_block.get("username")
            or payload.get("username")
            or "unknown"
        )
        eias_token = (
            data_block.get("eiasToken")
            or notification_block.get("eiasToken")
            or payload.get("eiasToken")
            or ""
        )

        # Change 4: Redact PII in logs — mask user_id to last 3 chars
        masked_user_id = (
            f"***{str(user_id)[-3:]}" if len(str(user_id)) > 3 else "***"
        )
        masked_username = (
            f"{str(username)[:2]}***" if len(str(username)) > 2 else "***"
        )

        logger.info(
            f"eBay account deletion notification received: "
            f"type={notification_type}, "
            f"notification_id={notification_id}, "
            f"user_id={masked_user_id}, "
            f"username={masked_username}"
        )

        # Step 4: Purge user-linked data from database
        records_purged = 0
        if user_id != "unknown" or username != "unknown":
            records_purged = self._purge_user_data(
                user_id=str(user_id),
                username=str(username),
                eias_token=str(eias_token),
            )

        # Step 5: Log to database for audit trail (PII-free)
        self._persist_notification(
            notification_id=notification_id,
            notification_type=notification_type,
        )

        return NotificationResult(
            success=True,
            message=f"Notification {notification_id} acknowledged",
            records_purged=records_purged,
        )

    # ------------------------------------------------------------------
    # Change 3: User Data Purge
    # ------------------------------------------------------------------

    def _purge_user_data(
        self,
        user_id: str,
        username: str,
        eias_token: str,
    ) -> int:
        """
        Purge all eBay user-linked data from REHU database.

        Deletes ebay_listings rows where raw_data contains the
        user's username, userId, or eiasToken. Cascading FK
        relationships handle product_matches, opportunity_scores,
        and watchlist_items automatically.

        Args:
            user_id: eBay user ID (numeric string).
            username: eBay username.
            eias_token: eBay persistent user token.

        Returns:
            Number of ebay_listings rows deleted.
        """
        try:
            from database.connection import get_db_context
            from models.ebay import EbayListing
            from sqlalchemy import or_

            with get_db_context() as db:
                # Build filter conditions for any matching identifier
                conditions = []
                if username and username != "unknown":
                    # raw_data is JSON; search for username in serialized form
                    conditions.append(
                        EbayListing.raw_data.contains(f'"{username}"')
                    )
                if user_id and user_id != "unknown":
                    conditions.append(
                        EbayListing.raw_data.contains(f'"{user_id}"')
                    )
                if eias_token:
                    conditions.append(
                        EbayListing.raw_data.contains(f'"{eias_token}"')
                    )

                if not conditions:
                    return 0

                query = db.query(EbayListing).filter(or_(*conditions))
                count = query.count()

                if count > 0:
                    # Delete matching listings
                    # FK cascades should handle dependent tables
                    query.delete(synchronize_session=False)
                    db.commit()

                    logger.info(
                        f"Purged {count} ebay_listings rows for "
                        f"user ***{user_id[-3:] if len(user_id) > 3 else '***'}"
                    )
                else:
                    logger.debug(
                        "No ebay_listings found matching deleted user"
                    )

                return count

        except Exception as e:
            logger.error(f"Failed to purge user data: {e}")
            # Do NOT raise — notification acknowledgement must succeed
            return 0

    # ------------------------------------------------------------------
    # Audit Persistence (PII-free)
    # ------------------------------------------------------------------

    def _persist_notification(
        self,
        notification_id: str,
        notification_type: str,
    ) -> None:
        """
        Persist notification metadata to database for audit.

        Stores only notification_id and type — NO user PII.
        Failures are logged but do not prevent acknowledgement.
        """
        try:
            from database.connection import get_db_context
            from models.audit import APIRequestLog

            with get_db_context() as db:
                log_entry = APIRequestLog(
                    service="ebay_compliance",
                    endpoint=f"/ebay/notifications/{notification_type}",
                    status_code=200,
                    response_time_ms=0,
                    was_cached=False,
                    cache_key=notification_id,
                )
                db.add(log_entry)
                db.commit()
                logger.debug(
                    f"Compliance notification {notification_id} persisted"
                )
        except Exception as e:
            logger.warning(
                f"Failed to persist compliance notification "
                f"{notification_id}: {e}"
            )