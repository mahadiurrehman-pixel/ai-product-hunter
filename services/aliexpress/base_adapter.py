"""
Abstract base adapter for AliExpress product data.

Defines the interface that all AliExpress adapters must implement.
Currently implemented by:
  - MockAliExpressAdapter (Phase 4, MVP)

Planned implementations:
  - OfficialAliExpressAdapter (requires affiliate program approval)
  - AffiliateAliExpressAdapter (alternative access method)
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from .models import AliExpressProduct


class BaseAliExpressAdapter(ABC):
    """
    Abstract interface for AliExpress product data access.

    All adapter implementations must provide these methods.
    The service layer depends on this interface, not on any
    specific implementation — allowing seamless switching from
    mock to real API without changing calling code.
    """

    @abstractmethod
    def search_products(
        self,
        query: str,
        limit: int = 10,
    ) -> List[AliExpressProduct]:
        """
        Search for AliExpress products matching a query.

        Args:
            query: Search keywords (normalized product title works best)
            limit: Maximum number of products to return

        Returns:
            List of AliExpressProduct objects.
            Empty list if no results found.
            Never raises on empty results — only raises on errors.

        Raises:
            AliExpressAdapterError: If search fails unexpectedly
        """

    @abstractmethod
    def get_product_details(
        self,
        product_id: str,
    ) -> Optional[AliExpressProduct]:
        """
        Get full details for a specific product.

        Args:
            product_id: AliExpress product ID

        Returns:
            AliExpressProduct if found, None if not found

        Raises:
            AliExpressAdapterError: If request fails unexpectedly
        """

    @abstractmethod
    def is_demo_mode(self) -> bool:
        """
        Whether this adapter uses simulated (mock) data.

        Returns:
            True if mock/demo data, False if real API data

        UI must display clear warning when is_demo_mode() is True.
        """

    def get_demo_warning(self) -> Optional[str]:
        """
        Get warning message to display when in demo mode.

        Returns:
            Warning string if demo mode, None if real data
        """
        if self.is_demo_mode():
            return (
                "⚠️ DEMO MODE: AliExpress data is simulated. "
                "Do not use these prices for real purchasing decisions. "
                "Real API requires AliExpress affiliate program approval."
            )
        return None