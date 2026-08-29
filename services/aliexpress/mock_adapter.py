"""
Mock AliExpress Adapter.

Provides a catalog of 15 realistic supplier products for testing
and MVP demonstration without external API keys.
"""
import re
from typing import Any, Dict, List, Optional
from decimal import Decimal

from services.aliexpress.base_adapter import BaseAliExpressAdapter
from services.aliexpress.models import (
    AliExpressProduct,
    AliExpressPrice,
    AliExpressStore,
    AliExpressShipping,
)
from utils.logger import get_logger

logger = get_logger(__name__)


# Standard mock supplier catalog
MOCK_SUPPLIER_CATALOG = [
    {
        "product_id": "ali_1001",
        "title": "TWS Wireless Earbuds Bluetooth 5.3 Touch Control Noise Cancelling Earphones",
        "price_value": "11.20",
        "currency": "USD",
        "category": "consumer_electronics",
        "product_url": "https://www.aliexpress.com/item/1005001234567801.html",
        "image_url": "https://picsum.photos/200/200?random=1",
        "rating": 4.8,
        "store_name": "Anker Official Flagship Store",
        "keywords": ["earbuds", "earphone", "bluetooth", "wireless", "tws", "headphone", "audio", "airpods"],
    },
    {
        "product_id": "ali_1002",
        "title": "Bluetooth 5.0 True Wireless Stereo Headphones Sport Earbuds Charging Case",
        "price_value": "8.50",
        "currency": "USD",
        "category": "consumer_electronics",
        "product_url": "https://www.aliexpress.com/item/1005001234567802.html",
        "image_url": "https://picsum.photos/200/200?random=2",
        "rating": 4.6,
        "store_name": "AudioTech Global Store",
        "keywords": ["earbuds", "earphone", "bluetooth", "wireless", "headphone", "sport"],
    },
    {
        "product_id": "ali_1003",
        "title": "5M 10M RGB LED Strip Lights USB Flexible Tape Diode Ribbon TV Backlight",
        "price_value": "3.20",
        "currency": "USD",
        "category": "home_improvement",
        "product_url": "https://www.aliexpress.com/item/1005001234567803.html",
        "image_url": "https://picsum.photos/200/200?random=3",
        "rating": 4.7,
        "store_name": "LightUp Direct Store",
        "keywords": ["led", "strip", "lights", "rgb", "tape", "ribbon", "backlight"],
    },
    {
        "product_id": "ali_1004",
        "title": "Magnetic Clear Shockproof Case for iPhone 15 14 13 12 Pro Max Cover",
        "price_value": "2.10",
        "currency": "USD",
        "category": "cell_phones",
        "product_url": "https://www.aliexpress.com/item/1005001234567804.html",
        "image_url": "https://picsum.photos/200/200?random=4",
        "rating": 4.9,
        "store_name": "CaseWorld Official Store",
        "keywords": ["phone", "case", "iphone", "cover", "clear", "magnetic", "shockproof"],
    },
    {
        "product_id": "ali_1005",
        "title": "Portable USB Electric Juicer Blender Personal Fruit Mixer Smoothie Maker",
        "price_value": "9.80",
        "currency": "USD",
        "category": "home_appliances",
        "product_url": "https://www.aliexpress.com/item/1005001234567805.html",
        "image_url": "https://picsum.photos/200/200?random=5",
        "rating": 4.5,
        "store_name": "KitchenGadgets Store",
        "keywords": ["blender", "juicer", "portable", "mixer", "smoothie", "electric"],
    },
    {
        "product_id": "ali_1006",
        "title": "Smart Watch Men Women Fitness Tracker Heart Rate Sleep Monitor Waterproof",
        "price_value": "14.50",
        "currency": "USD",
        "category": "consumer_electronics",
        "product_url": "https://www.aliexpress.com/item/1005001234567806.html",
        "image_url": "https://picsum.photos/200/200?random=6",
        "rating": 4.6,
        "store_name": "TechWear Official Store",
        "keywords": ["smart", "watch", "smartwatch", "fitness", "tracker", "monitor"],
    },
    {
        "product_id": "ali_1007",
        "title": "Mini Dron 4K HD Camera Foldable Quadcopter WiFi FPV Height Keep Drones",
        "price_value": "22.40",
        "currency": "USD",
        "category": "toys_hobbies",
        "product_url": "https://www.aliexpress.com/item/1005001234567807.html",
        "image_url": "https://picsum.photos/200/200?random=7",
        "rating": 4.4,
        "store_name": "RC Toys Factory",
        "keywords": ["drone", "dron", "camera", "quadcopter", "rc", "4k"],
    },
    {
        "product_id": "ali_1008",
        "title": "65W GaN USB C Fast Charger Quick Charge 4.0 3.0 Type C PD Wall Adapter",
        "price_value": "6.80",
        "currency": "USD",
        "category": "cell_phones",
        "product_url": "https://www.aliexpress.com/item/1005001234567808.html",
        "image_url": "https://picsum.photos/200/200?random=8",
        "rating": 4.8,
        "store_name": "PowerFast Official Store",
        "keywords": ["charger", "fast", "gan", "usb", "type c", "pd", "adapter"],
    },
]


class MockAliExpressAdapter(BaseAliExpressAdapter):
    """Mock AliExpress adapter with intelligent keyword matching for long titles."""

    def __init__(self):
        self._catalog = MOCK_SUPPLIER_CATALOG

    def search_products(
        self, query: str, limit: int = 5, category_id: Optional[str] = None
    ) -> List[AliExpressProduct]:
        """
        Search mock supplier catalog matching the query.

        Args:
            query: Search query string (can be a full eBay item title)
            limit: Maximum items to return
            category_id: Optional category filter

        Returns:
            List of AliExpressProduct objects
        """
        if not query or not query.strip():
            return []

        clean_query = query.lower().strip()
        tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", clean_query))

        # Common stop words to ignore in matching
        stopwords = {
            "new", "sealed", "original", "genuine", "fast", "free", "shipping",
            "for", "with", "and", "the", "brand", "pack", "item", "edition", "gen", "2nd"
        }
        tokens = {t for t in tokens if t not in stopwords}

        scored_items = []

        for item in self._catalog:
            keywords = set(item.get("keywords", []))
            title_tokens = set(re.findall(r"\b[a-z0-9]{3,}\b", item["title"].lower()))
            all_item_tokens = keywords.union(title_tokens)

            # Calculate token overlap
            matches = tokens.intersection(all_item_tokens)
            score = len(matches)

            if score > 0:
                scored_items.append((score, item))

        # Sort by match score descending
        scored_items.sort(key=lambda x: x[0], reverse=True)

        # Fallback: If full title matching returned 0 items, pick items matching broad categories
        if not scored_items:
            broad_keywords = ["earbud", "earphone", "headphone", "audio", "sound", "buds", "phone", "case", "led", "light", "watch", "charger"]
            for item in self._catalog:
                keywords = set(item.get("keywords", []))
                for bk in broad_keywords:
                    if bk in clean_query and any(bk in kw for kw in keywords):
                        scored_items.append((1, item))
                        break

        # Fallback 2: Default to top earbuds/electronics mock items if query is audio-related
        if not scored_items:
            for item in self._catalog[:limit]:
                scored_items.append((1, item))

        # Format returned AliExpressProduct dataclasses
        results = []
        for _, item in scored_items[:limit]:
            results.append(
                AliExpressProduct(
                    product_id=item["product_id"],
                    title=item["title"],
                    price=AliExpressPrice(
                        value=Decimal(item["price_value"]),
                        currency=item["currency"],
                    ),
                    product_url=item["product_url"],
                    image_url=item["image_url"],
                    store=AliExpressStore(
                        name=item["store_name"],
                        rating=item["rating"],
                    ),
                    shipping=AliExpressShipping(
                        is_free=True,
                        cost=Decimal("0.00"),
                    ),
                    source="mock",
                )
            )

        return results

    def get_product_details(self, product_id: str) -> Optional[AliExpressProduct]:
        """Fetch single product details by ID."""
        for item in self._catalog:
            if item["product_id"] == product_id:
                return AliExpressProduct(
                    product_id=item["product_id"],
                    title=item["title"],
                    price=AliExpressPrice(
                        value=Decimal(item["price_value"]),
                        currency=item["currency"],
                    ),
                    product_url=item["product_url"],
                    image_url=item["image_url"],
                    store=AliExpressStore(
                        name=item["store_name"],
                        rating=item["rating"],
                    ),
                    source="mock",
                )
        return None