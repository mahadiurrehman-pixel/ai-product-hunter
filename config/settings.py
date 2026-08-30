"""
Application Settings and Configuration Management.

Loads configuration from environment variables with validation.
"""
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings.

    Loads from environment variables and .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------
    app_mode: Literal["development", "production"] = "development"
    app_name: str = "AI Product Hunter"
    app_version: str = "0.1.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # -------------------------------------------------------------------------
    # eBay API Configuration
    # -------------------------------------------------------------------------
    ebay_environment: Literal["sandbox", "production"] = "sandbox"
    ebay_app_id: str = Field(default="", description="eBay Application ID")
    ebay_cert_id: str = Field(default="", description="eBay Certificate ID")
    ebay_marketplace_id: str = Field(
        default="EBAY_US",
        description=(
            "eBay regional marketplace ID. "
            "Supported: EBAY_US, EBAY_GB, EBAY_DE, EBAY_AU, EBAY_CA"
        ),
    )
    ebay_oauth_scope: str = "https://api.ebay.com/oauth/api_scope"

    # Rate limiting
    ebay_rate_limit_per_day: int = 5000
    ebay_rate_limit_per_second: int = 5

    # eBay Compliance (Required for Production keyset activation)
    ebay_verification_token: str = ""
    ebay_notification_endpoint_url: str = ""
    # Internal Microservice Auth (Phase M1)
    internal_auth_secret: str = "dev_internal_secret_change_in_production"
    @field_validator("ebay_marketplace_id")
    @classmethod
    def validate_marketplace_id(cls, v: str) -> str:
        """
        Validate that marketplace ID is supported.

        Validates against official supported eBay marketplace IDs.
        Rejects unsupported marketplace values with clear error.
        Does not import from services layer to avoid circular dependencies.
        """
        if not v:
            return "EBAY_US"

        normalized = str(v).strip().upper()
        valid = {"EBAY_US", "EBAY_GB", "EBAY_DE", "EBAY_AU", "EBAY_CA"}
        if normalized not in valid:
            supported = ", ".join(sorted(valid))
            raise ValueError(
                f"Unsupported eBay marketplace: '{v}'. "
                f"Supported marketplaces: {supported}"
            )
        return normalized

    @property
    def ebay_marketplace(self):
        """
        Get the configured eBay marketplace as an enum.

        Returns:
            EbayMarketplace enum member
        """
        from services.ebay.marketplace import EbayMarketplace

        return EbayMarketplace.from_id(self.ebay_marketplace_id)

    # -------------------------------------------------------------------------
    # AliExpress Configuration
    # -------------------------------------------------------------------------
    aliexpress_mode: Literal["mock", "production"] = "mock"
    aliexpress_api_key: str = ""
    aliexpress_tracking_id: str = ""

    # -------------------------------------------------------------------------
    # Database Configuration
    # -------------------------------------------------------------------------
    database_url: str = "sqlite:///./data/product_hunter.db"
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # -------------------------------------------------------------------------
    # Cache Configuration
    # -------------------------------------------------------------------------
    cache_enabled: bool = True
    cache_ttl_hours: int = 1
    cache_max_size: int = 1000
    cache_product_details_ttl_hours: int = 6
    cache_search_results_ttl_hours: int = 1
    # Cache TTL in seconds (overrides hour-based settings if set)
    ebay_search_cache_ttl_seconds: int = 86400   # 24 hours
    ebay_item_cache_ttl_seconds: int = 86400     # 24 hours
    # Retry configuration
    ebay_max_retries: int = 3
    ebay_retry_base_delay_seconds: float = 1.0
    ebay_retry_max_delay_seconds: float = 30.0
    # -------------------------------------------------------------------------
    # Search & Matching Configuration
    # -------------------------------------------------------------------------
    max_search_results: int = 50
    max_aliexpress_matches: int = 10
    min_match_score: float = 0.60
    semantic_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # -------------------------------------------------------------------------
    # Scoring Configuration
    # -------------------------------------------------------------------------
    scoring_weight_market: float = 0.30
    scoring_weight_competition: float = 0.20
    scoring_weight_economics: float = 0.30
    scoring_weight_match: float = 0.15
    scoring_weight_confidence: float = 0.05

    @field_validator(
        "scoring_weight_market",
        "scoring_weight_competition",
        "scoring_weight_economics",
        "scoring_weight_match",
        "scoring_weight_confidence",
    )
    @classmethod
    def validate_weight(cls, v: float) -> float:
        """Ensure weights are between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError(f"Weight must be between 0 and 1, got {v}")
        return v

    # -------------------------------------------------------------------------
    # Profit Calculation Defaults
    # -------------------------------------------------------------------------
    ebay_final_value_fee_percent: float = 12.9
    ebay_final_value_fee_fixed: float = 0.30
    payment_fee_percent: float = 3.49
    payment_fee_fixed: float = 0.49
    default_shipping_cost_estimate: float = 5.00
    default_currency: str = "USD"

    # -------------------------------------------------------------------------
    # Directory Paths
    # -------------------------------------------------------------------------
    data_dir: Path = Path("./data")
    cache_dir: Path = Path("./data/cache")
    logs_dir: Path = Path("./logs")
    exports_dir: Path = Path("./data/exports")

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_mode == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_mode == "production"

    @property
    def ebay_api_base_url(self) -> str:
        """Get eBay API base URL based on environment."""
        if self.ebay_environment == "sandbox":
            return "https://api.sandbox.ebay.com"
        return "https://api.ebay.com"

    @property
    def ebay_oauth_url(self) -> str:
        """Get eBay OAuth URL."""
        return f"{self.ebay_api_base_url}/identity/v1/oauth2/token"

    @property
    def scoring_weights(self) -> dict:
        """Get all scoring weights as dictionary."""
        return {
            "market_signals": self.scoring_weight_market,
            "competition_signals": self.scoring_weight_competition,
            "economics_signals": self.scoring_weight_economics,
            "supplier_match_signals": self.scoring_weight_match,
            "confidence_bonus": self.scoring_weight_confidence,
        }

    def validate_scoring_weights(self) -> None:
        """Validate that scoring weights sum to 1.0."""
        total = sum(self.scoring_weights.values())
        if not 0.99 <= total <= 1.01:
            raise ValueError(
                f"Scoring weights must sum to 1.0, got {total}. "
                f"Weights: {self.scoring_weights}"
            )

    def ensure_directories(self) -> None:
        """Ensure required data and cache directories exist."""
        directories = [
            Path("data"),
            Path("data/cache"),
            Path("data/backups"),
            Path("/app/data") if Path("/app").exists() else Path("data"),
            Path("/app/data/cache") if Path("/app").exists() else Path("data/cache"),
        ]
        for directory in directories:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as e:
                # In container/cloud volume environments, permissions are handled by entrypoint
                pass

    def model_post_init(self, __context) -> None:
        """Post-initialization validation and setup."""
        self.validate_scoring_weights()
        self.ensure_directories()


# Global settings instance
settings = Settings()
