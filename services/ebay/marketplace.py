"""
eBay marketplace/region definitions.

Provides the EbayMarketplace enum with metadata for each supported
regional eBay marketplace.

Currently supported (5 marketplaces):
    EBAY_US — eBay United States (USD)
    EBAY_GB — eBay United Kingdom (GBP)
    EBAY_DE — eBay Germany (EUR)
    EBAY_AU — eBay Australia (AUD)
    EBAY_CA — eBay Canada (CAD)

Marketplace IDs are the official eBay Browse API values used in the
X-EBAY-C-MARKETPLACE-ID request header. Do not modify these values.

Reference:
https://developer.ebay.com/api-docs/static/rest-request-components.html#marketpl
"""
from dataclasses import dataclass
from enum import Enum
from typing import List


@dataclass(frozen=True)
class MarketplaceMetadata:
    """
    Metadata associated with an eBay marketplace.

    Fields:
        display_name: User-facing name for UI display
        currency: ISO 4217 currency code for the marketplace's native currency
        region: Human-readable region name
    """

    display_name: str
    currency: str
    region: str


class EbayMarketplace(str, Enum):
    """
    Supported eBay regional marketplaces.

    Inherits from str so the enum value can be used directly as the
    X-EBAY-C-MARKETPLACE-ID header value without conversion.
    """

    US = "EBAY_US"
    UK = "EBAY_GB"
    GERMANY = "EBAY_DE"
    AUSTRALIA = "EBAY_AU"
    CANADA = "EBAY_CA"

    @property
    def metadata(self) -> MarketplaceMetadata:
        """Get metadata for this marketplace."""
        return _METADATA[self]

    @property
    def display_name(self) -> str:
        """User-facing display name (e.g., 'eBay United States')."""
        return self.metadata.display_name

    @property
    def currency(self) -> str:
        """ISO 4217 currency code (e.g., 'USD')."""
        return self.metadata.currency

    @property
    def region(self) -> str:
        """Human-readable region name (e.g., 'United States')."""
        return self.metadata.region

    @classmethod
    def from_id(cls, marketplace_id: str) -> "EbayMarketplace":
        """
        Parse a marketplace ID string into an EbayMarketplace enum.

        Args:
            marketplace_id: eBay marketplace ID (e.g., "EBAY_US")

        Returns:
            Corresponding EbayMarketplace enum member

        Raises:
            ValueError: If marketplace_id is not supported
        """
        if not marketplace_id:
            raise ValueError("Marketplace ID cannot be empty")

        normalized = str(marketplace_id).strip().upper()

        for member in cls:
            if member.value == normalized:
                return member

        supported = ", ".join(m.value for m in cls)
        raise ValueError(
            f"Unsupported eBay marketplace: '{marketplace_id}'. "
            f"Supported marketplaces: {supported}"
        )

    @classmethod
    def supported_ids(cls) -> List[str]:
        """
        Get list of all supported marketplace IDs.

        Returns:
            List of marketplace ID strings, e.g. ["EBAY_US", "EBAY_GB", ...]
        """
        return [m.value for m in cls]

    @classmethod
    def all_metadata(cls) -> List[dict]:
        """
        Get all marketplaces with their metadata.

        Useful for building UI dropdowns without duplicating information.

        Returns:
            List of dicts with id, display_name, currency, region
        """
        return [
            {
                "id": m.value,
                "display_name": m.display_name,
                "currency": m.currency,
                "region": m.region,
            }
            for m in cls
        ]


# Metadata table — single source of truth for marketplace properties.
_METADATA = {
    EbayMarketplace.US: MarketplaceMetadata(
        display_name="eBay United States",
        currency="USD",
        region="United States",
    ),
    EbayMarketplace.UK: MarketplaceMetadata(
        display_name="eBay United Kingdom",
        currency="GBP",
        region="United Kingdom",
    ),
    EbayMarketplace.GERMANY: MarketplaceMetadata(
        display_name="eBay Germany",
        currency="EUR",
        region="Germany",
    ),
    EbayMarketplace.AUSTRALIA: MarketplaceMetadata(
        display_name="eBay Australia",
        currency="AUD",
        region="Australia",
    ),
    EbayMarketplace.CANADA: MarketplaceMetadata(
        display_name="eBay Canada",
        currency="CAD",
        region="Canada",
    ),
}