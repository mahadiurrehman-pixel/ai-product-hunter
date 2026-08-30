"""
eBay OAuth 2.0 authentication.

Implements Client Credentials grant flow for application-level access.
Official docs:
https://developer.ebay.com/api-docs/static/oauth-client-credentials-grant.html
"""
import base64
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config import settings
from utils.logger import get_logger
from .exceptions import EbayAuthenticationError, EbayNetworkError

logger = get_logger(__name__)


class EbayAuth:
    """
    eBay OAuth 2.0 authentication manager.

    Uses Client Credentials grant for application-level access token.
    Tokens are cached and automatically refreshed when expired.
    """

    def __init__(
        self,
        app_id: Optional[str] = None,
        cert_id: Optional[str] = None,
        environment: Optional[str] = None,
    ):
        """
        Initialize eBay authentication.

        Args:
            app_id: eBay Application ID (defaults to settings).
                    Pass "" explicitly to force no credentials.
            cert_id: eBay Certificate ID (defaults to settings).
                     Pass "" explicitly to force no credentials.
            environment: 'sandbox' or 'production' (defaults to settings)
        """
        # Use explicit value if provided (including empty string),
        # otherwise fall back to settings.
        # This allows tests to pass "" to explicitly test missing credentials.
        self.app_id = app_id if app_id is not None else settings.ebay_app_id
        self.cert_id = cert_id if cert_id is not None else settings.ebay_cert_id
        self.environment = environment or settings.ebay_environment

        # Token cache
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

        # Validate credentials are provided
        if not self.app_id or not self.cert_id:
            logger.warning(
                "eBay credentials not configured. "
                "Set EBAY_APP_ID and EBAY_CERT_ID in .env file."
            )

    @property
    def oauth_url(self) -> str:
        """Get OAuth token endpoint URL based on environment."""
        base_url = settings.ebay_api_base_url
        return f"{base_url}/identity/v1/oauth2/token"

    def _get_auth_header(self) -> str:
        """
        Generate Basic Authorization header.

        Returns:
            Base64-encoded "App ID:Cert ID"

        Raises:
            EbayAuthenticationError: If credentials are missing
        """
        if not self.app_id or not self.cert_id:
            raise EbayAuthenticationError(
                "eBay credentials not configured",
                details={
                    "app_id_present": bool(self.app_id),
                    "cert_id_present": bool(self.cert_id),
                },
            )

        # Combine credentials
        credentials = f"{self.app_id}:{self.cert_id}"

        # Base64 encode
        encoded = base64.b64encode(credentials.encode()).decode()

        return f"Basic {encoded}"

    def get_application_token(self, force_refresh: bool = False) -> str:
        """
        Get valid application access token.

        Returns cached token if still valid, otherwise requests new token.

        Args:
            force_refresh: Force token refresh even if cached token valid

        Returns:
            Valid access token

        Raises:
            EbayAuthenticationError: If authentication fails
            EbayNetworkError: If network request fails
        """
        # Return cached token if still valid
        if not force_refresh and self._is_token_valid():
            logger.debug("Using cached eBay access token")
            return self._access_token  # type: ignore

        # Request new token
        logger.info(
            f"Requesting new eBay access token ({self.environment})"
        )

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    url=self.oauth_url,
                    headers={
                        "Content-Type": (
                            "application/x-www-form-urlencoded"
                        ),
                        "Authorization": self._get_auth_header(),
                    },
                    data={
                        "grant_type": "client_credentials",
                        "scope": settings.ebay_oauth_scope,
                    },
                )

                # Handle authentication errors
                if response.status_code == 401:
                    logger.error(
                        "eBay authentication failed - invalid credentials"
                    )
                    raise EbayAuthenticationError(
                        "Invalid eBay credentials",
                        details={"status_code": 401},
                    )

                if response.status_code != 200:
                    logger.error(
                        f"eBay OAuth request failed: "
                        f"{response.status_code}"
                    )
                    raise EbayAuthenticationError(
                        f"OAuth request failed with status "
                        f"{response.status_code}",
                        details={
                            "status_code": response.status_code,
                            "response": response.text[:500],
                        },
                    )

                # Parse response
                data = response.json()

                if "access_token" not in data:
                    raise EbayAuthenticationError(
                        "OAuth response missing access_token",
                        details={"response_keys": list(data.keys())},
                    )

                # Cache token
                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 7200)
                self._token_expires_at = datetime.utcnow() + timedelta(
                    seconds=expires_in - 60  # Refresh 1 minute early
                )

                logger.info(
                    f"eBay access token obtained, expires in {expires_in}s"
                )

                return self._access_token

        # Re-raise our custom exceptions without wrapping
        except EbayAuthenticationError:
            raise

        except httpx.TimeoutException as e:
            logger.error(f"eBay OAuth request timeout: {e}")
            raise EbayNetworkError(
                "OAuth request timeout", details={"error": str(e)}
            )

        except httpx.RequestError as e:
            logger.error(f"eBay OAuth network error: {e}")
            raise EbayNetworkError(
                "OAuth network error", details={"error": str(e)}
            )

        # Only unexpected exceptions get wrapped
        except Exception as e:
            logger.error(f"Unexpected OAuth error: {e}")
            raise EbayAuthenticationError(
                f"Unexpected authentication error: {str(e)}"
            )

    def _is_token_valid(self) -> bool:
        """
        Check if cached token is still valid.

        Returns:
            True if token exists and not expired
        """
        if not self._access_token or not self._token_expires_at:
            return False

        return datetime.utcnow() < self._token_expires_at

    def clear_token(self) -> None:
        """Clear cached token (useful for testing or forcing refresh)."""
        self._access_token = None
        self._token_expires_at = None
        logger.debug("eBay access token cache cleared")