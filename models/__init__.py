"""
Database models for AI Product Hunter.
"""
from .base import Base
from .ebay import EbayListing
from .aliexpress import AliExpressListing
from .product import NormalizedProduct
from .match import ProductMatch
from .score import OpportunityScoreRecord
from .watchlist import WatchlistItem
from .audit import APIRequestLog

__all__ = [
    "Base",
    "EbayListing",
    "AliExpressListing",
    "NormalizedProduct",
    "ProductMatch",
    "OpportunityScoreRecord",
    "WatchlistItem",
    "APIRequestLog",
]
