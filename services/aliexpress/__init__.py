"""
AliExpress integration services.

MVP uses MockAliExpressAdapter — all data is simulated.
Switch to OfficialAliExpressAdapter when real credentials available.

Usage:
    from services.aliexpress import get_adapter

    adapter = get_adapter()  # Returns correct adapter based on settings
    products = adapter.search_products("wireless earbuds", limit=10)

    if adapter.is_demo_mode():
        print(adapter.get_demo_warning())
"""
from .models import AliExpressProduct, AliExpressPrice, AliExpressStore, AliExpressShipping
from .base_adapter import BaseAliExpressAdapter
from .mock_adapter import MockAliExpressAdapter
from .repository import AliExpressRepository
from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def get_adapter() -> BaseAliExpressAdapter:
    """
    Factory function — returns appropriate adapter based on settings.

    Reads ALIEXPRESS_MODE from .env:
    - "mock" → MockAliExpressAdapter (default, no credentials needed)
    - "production" → raises NotImplementedError (future implementation)

    Returns:
        Configured AliExpress adapter instance
    """
    mode = settings.aliexpress_mode

    if mode == "mock":
        logger.info("AliExpress adapter: MockAliExpressAdapter (DEMO MODE)")
        return MockAliExpressAdapter()

    elif mode == "production":
        logger.error(
            "AliExpress production mode not yet implemented. "
            "Set ALIEXPRESS_MODE=mock in .env to use demo mode."
        )
        raise NotImplementedError(
            "AliExpress production adapter not implemented in MVP. "
            "Requires affiliate program approval. "
            "Set ALIEXPRESS_MODE=mock to continue."
        )

    else:
        logger.warning(
            f"Unknown ALIEXPRESS_MODE '{mode}'. "
            "Falling back to mock adapter."
        )
        return MockAliExpressAdapter()


__all__ = [
    "AliExpressProduct",
    "AliExpressPrice",
    "AliExpressStore",
    "AliExpressShipping",
    "BaseAliExpressAdapter",
    "MockAliExpressAdapter",
    "AliExpressRepository",
    "get_adapter",
]