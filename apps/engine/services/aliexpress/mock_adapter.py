"""
Mock AliExpress Adapter.

Provides a catalog of realistic supplier products for testing
and MVP demonstration without external API keys.
"""
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

from services.aliexpress.base_adapter import BaseAliExpressAdapter
from services.aliexpress.models import (
    AliExpressProduct,
    AliExpressPrice,
    AliExpressStore,
    AliExpressShipping,
)
from utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_MOCK_PATH = Path("services/aliexpress/data/mock_products.json")


class MockAliExpressAdapter(BaseAliExpressAdapter):
    """
    Mock AliExpress adapter with intelligent keyword matching for long titles.
    Conforms strictly to BaseAliExpressAdapter and model dataclasses.
    """

    def __init__(self, mock_data_path: Optional[Union[str, Path]] = None):
        self.mock_data_path = Path(mock_data_path) if mock_data_path is not None else None
        self._products: List[Dict[str, Any]] = []
        self._is_loaded: bool = False
        self._load_mock_data()

    def is_demo_mode(self) -> bool:
        """Return whether adapter is running in demo/mock mode."""
        return True

    def get_demo_warning(self) -> str:
        """Return demo warning notice."""
        return "AliExpress adapter is running in MOCK mode (DEMO MODE) with simulated product data."

    def _load_mock_data(self) -> List[Dict[str, Any]]:
        """Load mock products from data file or fallback catalogue."""
        if self._is_loaded:
            return self._products

        if self.mock_data_path is not None:
            if not self.mock_data_path.exists():
                self._products = []
                self._is_loaded = True
                return []
            try:
                with open(self.mock_data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._products = data if isinstance(data, list) else []
                    self._is_loaded = True
                    return self._products
            except Exception:
                self._products = []
                self._is_loaded = True
                return []

        if _DEFAULT_MOCK_PATH.exists():
            try:
                with open(_DEFAULT_MOCK_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and len(data) == 15:
                        self._products = data
                        self._is_loaded = True
                        return self._products
            except Exception:
                pass

        self._products = self._build_default_catalog()
        self._is_loaded = True
        return self._products

    def _build_default_catalog(self) -> List[Dict[str, Any]]:
        return [
            {
                "product_id": "ali_001",
                "title": "TWS Wireless Earbuds Bluetooth 5.3 Touch Control Noise Cancelling Earphones",
                "price_value": "11.20",
                "original_value": "22.40",
                "currency": "USD",
                "category": "audio",
                "product_url": "https://www.aliexpress.com/item/1005001234567801.html",
                "image_url": "https://picsum.photos/200/200?random=1",
                "rating_score": 4.8,
                "review_count": 1520,
                "orders_count": 5200,
                "store_name": "Anker Official Flagship Store",
                "store_id": "store_001",
                "positive_feedback_rate": 98.5,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 12,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["earbuds", "earphone", "bluetooth", "wireless", "tws", "headphone", "audio", "airpods"],
                "source": "mock",
            },
            {
                "product_id": "ali_002",
                "title": "Bluetooth 5.0 True Wireless Stereo Headphones Sport Earbuds Charging Case",
                "price_value": "8.50",
                "original_value": "17.00",
                "currency": "USD",
                "category": "audio",
                "product_url": "https://www.aliexpress.com/item/1005001234567802.html",
                "image_url": "https://picsum.photos/200/200?random=2",
                "rating_score": 4.6,
                "review_count": 850,
                "orders_count": 3100,
                "store_name": "AudioTech Global Store",
                "store_id": "store_002",
                "positive_feedback_rate": 97.2,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 14,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["earbuds", "earphone", "bluetooth", "wireless", "headphone", "sport"],
                "source": "mock",
            },
            {
                "product_id": "ali_003",
                "title": "5M 10M RGB LED Strip Lights USB Flexible Tape Diode Ribbon TV Backlight",
                "price_value": "3.20",
                "original_value": "6.40",
                "currency": "USD",
                "category": "home_improvement",
                "product_url": "https://www.aliexpress.com/item/1005001234567803.html",
                "image_url": "https://picsum.photos/200/200?random=3",
                "rating_score": 4.7,
                "review_count": 2100,
                "orders_count": 8900,
                "store_name": "LightUp Direct Store",
                "store_id": "store_003",
                "positive_feedback_rate": 98.1,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 10,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["led", "strip", "lights", "rgb", "tape", "ribbon", "backlight"],
                "source": "mock",
            },
            {
                "product_id": "ali_004",
                "title": "Magnetic Clear Shockproof Case for iPhone 15 14 13 12 Pro Max Cover",
                "price_value": "2.10",
                "original_value": "4.20",
                "currency": "USD",
                "category": "cell_phones",
                "product_url": "https://www.aliexpress.com/item/1005001234567804.html",
                "image_url": "https://picsum.photos/200/200?random=4",
                "rating_score": 4.9,
                "review_count": 4300,
                "orders_count": 15000,
                "store_name": "CaseWorld Official Store",
                "store_id": "store_004",
                "positive_feedback_rate": 99.0,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 15,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["phone", "case", "iphone", "cover", "clear", "magnetic", "shockproof"],
                "source": "mock",
            },
            {
                "product_id": "ali_005",
                "title": "Portable USB Electric Juicer Blender Personal Fruit Mixer Smoothie Maker",
                "price_value": "9.80",
                "original_value": "19.60",
                "currency": "USD",
                "category": "home_appliances",
                "product_url": "https://www.aliexpress.com/item/1005001234567805.html",
                "image_url": "https://picsum.photos/200/200?random=5",
                "rating_score": 4.5,
                "review_count": 640,
                "orders_count": 2200,
                "store_name": "KitchenGadgets Store",
                "store_id": "store_005",
                "positive_feedback_rate": 96.5,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 16,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["blender", "juicer", "portable", "mixer", "smoothie", "electric"],
                "source": "mock",
            },
            {
                "product_id": "ali_006",
                "title": "Smart Watch Men Women Fitness Tracker Heart Rate Sleep Monitor Waterproof",
                "price_value": "14.50",
                "original_value": "29.00",
                "currency": "USD",
                "category": "consumer_electronics",
                "product_url": "https://www.aliexpress.com/item/1005001234567806.html",
                "image_url": "https://picsum.photos/200/200?random=6",
                "rating_score": 4.6,
                "review_count": 1890,
                "orders_count": 6400,
                "store_name": "TechWear Official Store",
                "store_id": "store_006",
                "positive_feedback_rate": 97.8,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 12,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["smart", "watch", "smartwatch", "fitness", "tracker", "monitor"],
                "source": "mock",
            },
            {
                "product_id": "ali_007",
                "title": "Mini Dron 4K HD Camera Foldable Quadcopter WiFi FPV Height Keep Drones",
                "price_value": "22.40",
                "original_value": "44.80",
                "currency": "USD",
                "category": "toys_hobbies",
                "product_url": "https://www.aliexpress.com/item/1005001234567807.html",
                "image_url": "https://picsum.photos/200/200?random=7",
                "rating_score": 4.4,
                "review_count": 510,
                "orders_count": 1800,
                "store_name": "RC Toys Factory",
                "store_id": "store_007",
                "positive_feedback_rate": 95.8,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 18,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["drone", "dron", "camera", "quadcopter", "rc", "4k"],
                "source": "mock",
            },
            {
                "product_id": "ali_008",
                "title": "65W GaN USB C Fast Charger Quick Charge 4.0 3.0 Type C PD Wall Adapter",
                "price_value": "6.80",
                "original_value": "13.60",
                "currency": "USD",
                "category": "cell_phones",
                "product_url": "https://www.aliexpress.com/item/1005001234567808.html",
                "image_url": "https://picsum.photos/200/200?random=8",
                "rating_score": 4.8,
                "review_count": 3200,
                "orders_count": 11000,
                "store_name": "PowerFast Official Store",
                "store_id": "store_008",
                "positive_feedback_rate": 98.9,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 11,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["charger", "fast", "gan", "usb", "type c", "pd", "adapter"],
                "source": "mock",
            },
            {
                "product_id": "ali_009",
                "title": "Dual Mode Bluetooth Ergonomic Wireless Mouse Silent Rechargeable Optical Mice",
                "price_value": "5.40",
                "original_value": "10.80",
                "currency": "USD",
                "category": "electronics",
                "product_url": "https://www.aliexpress.com/item/1005001234567809.html",
                "image_url": "https://picsum.photos/200/200?random=9",
                "rating_score": 4.7,
                "review_count": 1420,
                "orders_count": 4800,
                "store_name": "Peripherals Hub",
                "store_id": "store_009",
                "positive_feedback_rate": 97.6,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 13,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["mouse", "mice", "bluetooth", "wireless", "ergonomic", "optical"],
                "source": "mock",
            },
            {
                "product_id": "ali_010",
                "title": "RGB Mechanical Gaming Keyboard 87 Keys Blue Red Switch Wired USB Keyboards",
                "price_value": "18.90",
                "original_value": "37.80",
                "currency": "USD",
                "category": "electronics",
                "product_url": "https://www.aliexpress.com/item/1005001234567810.html",
                "image_url": "https://picsum.photos/200/200?random=10",
                "rating_score": 4.8,
                "review_count": 980,
                "orders_count": 3400,
                "store_name": "GamerGear Official Store",
                "store_id": "store_010",
                "positive_feedback_rate": 98.4,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 14,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["keyboard", "gaming", "mechanical", "rgb", "switch", "wired"],
                "source": "mock",
            },
            {
                "product_id": "ali_011",
                "title": "1080P Full HD Webcam with Microphone USB Web Camera for PC Desktop Laptop",
                "price_value": "7.90",
                "original_value": "15.80",
                "currency": "USD",
                "category": "electronics",
                "product_url": "https://www.aliexpress.com/item/1005001234567811.html",
                "image_url": "https://picsum.photos/200/200?random=11",
                "rating_score": 4.6,
                "review_count": 760,
                "orders_count": 2700,
                "store_name": "VisionTech Digital Store",
                "store_id": "store_011",
                "positive_feedback_rate": 96.9,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 12,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["webcam", "camera", "microphone", "usb", "streaming", "video"],
                "source": "mock",
            },
            {
                "product_id": "ali_012",
                "title": "Aluminum Foldable Laptop Stand Ergonomic Portable Cooling Notebook Holder",
                "price_value": "6.50",
                "original_value": "13.00",
                "currency": "USD",
                "category": "electronics",
                "product_url": "https://www.aliexpress.com/item/1005001234567812.html",
                "image_url": "https://picsum.photos/200/200?random=12",
                "rating_score": 4.9,
                "review_count": 2800,
                "orders_count": 9500,
                "store_name": "StandPro Accessories Store",
                "store_id": "store_012",
                "positive_feedback_rate": 99.2,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 10,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["laptop", "stand", "holder", "aluminum", "cooling", "portable"],
                "source": "mock",
            },
            {
                "product_id": "ali_013",
                "title": "8 in 1 USB C Hub HDMI 4K USB 3.0 Multiport Adapter Type C Docking Station",
                "price_value": "12.30",
                "original_value": "24.60",
                "currency": "USD",
                "category": "electronics",
                "product_url": "https://www.aliexpress.com/item/1005001234567813.html",
                "image_url": "https://picsum.photos/200/200?random=13",
                "rating_score": 4.7,
                "review_count": 1650,
                "orders_count": 5800,
                "store_name": "ConnectHub Tech Store",
                "store_id": "store_013",
                "positive_feedback_rate": 98.0,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 11,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["hub", "adapter", "dock", "hdmi", "type c", "usb"],
                "source": "mock",
            },
            {
                "product_id": "ali_014",
                "title": "15W Magnetic Wireless Car Charger Auto Clamping Air Vent Phone Holder Mount",
                "price_value": "8.90",
                "original_value": "17.80",
                "currency": "USD",
                "category": "cell_phones",
                "product_url": "https://www.aliexpress.com/item/1005001234567814.html",
                "image_url": "https://picsum.photos/200/200?random=14",
                "rating_score": 4.5,
                "review_count": 890,
                "orders_count": 3100,
                "store_name": "AutoDrive Accessories",
                "store_id": "store_014",
                "positive_feedback_rate": 96.8,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 15,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["car", "charger", "wireless", "mount", "holder", "magnetic"],
                "source": "mock",
            },
            {
                "product_id": "ali_015",
                "title": "Stainless Steel Insulated Water Bottle Vacuum Flask Thermal Sport Drink Cup",
                "price_value": "5.20",
                "original_value": "10.40",
                "currency": "USD",
                "category": "sports_outdoors",
                "product_url": "https://www.aliexpress.com/item/1005001234567815.html",
                "image_url": "https://picsum.photos/200/200?random=15",
                "rating_score": 4.8,
                "review_count": 2100,
                "orders_count": 7200,
                "store_name": "HydroLife Outdoor Store",
                "store_id": "store_015",
                "positive_feedback_rate": 98.7,
                "shipping_cost": "0.00",
                "estimated_delivery_days": 13,
                "shipping_method": "AliExpress Standard Shipping",
                "keywords": ["bottle", "flask", "thermos", "water", "stainless", "insulated"],
                "source": "mock",
            },
        ]

    def _tokenize(self, text: Union[str, List[str]]) -> List[str]:
        """Tokenize string or pass through list of tokens."""
        if isinstance(text, list):
            return [str(t).lower() for t in text if str(t).strip()]
        if not text:
            return []
        cleaned = str(text).lower().strip()
        tokens = re.findall(r"\b[a-z0-9]{3,}\b", cleaned)
        stopwords = {
            "new", "sealed", "original", "genuine", "fast", "free", "shipping",
            "for", "with", "and", "the", "brand", "pack", "item", "edition", "gen", "2nd"
        }
        return [t for t in tokens if t not in stopwords]

    def _calculate_relevance(self, query: Union[str, List[str]], item: dict) -> float:
        """Calculate keyword relevance score between query and product."""
        if not query:
            return 0.0

        if isinstance(query, list):
            query_tokens = set(str(t).lower() for t in query if str(t).strip())
            query_str = " ".join(query_tokens)
        else:
            cleaned = str(query).strip()
            if not cleaned:
                return 0.0
            query_tokens = set(self._tokenize(cleaned)) or set(cleaned.lower().split())
            query_str = cleaned.lower()

        if not query_tokens:
            return 0.0

        title_str = str(item.get("title", "")).lower()
        title_tokens = set(self._tokenize(title_str)) or set(title_str.split())
        raw_keywords = item.get("keywords", [])
        if isinstance(raw_keywords, list):
            item_keywords = set(str(k).lower() for k in raw_keywords)
        else:
            item_keywords = set(self._tokenize(str(raw_keywords)))

        score = 0.0

        # Title matches (+3.0 per matching token)
        title_matches = query_tokens.intersection(title_tokens)
        score += len(title_matches) * 3.0

        # Keyword matches (+2.0 per matching token)
        kw_matches = query_tokens.intersection(item_keywords)
        score += len(kw_matches) * 2.0

        # Attribute matches (+2.0 per matching token)
        attrs = item.get("attributes", {})
        if isinstance(attrs, dict):
            for attr_val in attrs.values():
                attr_tokens = set(str(attr_val).lower().split())
                score += len(query_tokens.intersection(attr_tokens)) * 2.0

        # Exact query phrase in title (+5.0)
        if query_str and len(query_str) > 3 and query_str in title_str:
            score += 5.0

        # Category match bonus (+2.0)
        category = str(item.get("category", "")).lower()
        if any(q in category for q in query_tokens):
            score += 2.0

        return float(score)

    def search_products(
        self, query: str, limit: int = 5, category_id: Optional[str] = None
    ) -> List[AliExpressProduct]:
        """Search mock catalog matching query."""
        if not query or not str(query).strip():
            return []

        products = self._load_mock_data()
        if not products:
            return []

        scored_items = []
        for item in products:
            score = self._calculate_relevance(query, item)
            if score > 0:
                scored_items.append((score, item))

        scored_items.sort(key=lambda x: x[0], reverse=True)

        # Fallback 1: Broad keyword matching for long live eBay titles
        if not scored_items:
            clean_query = str(query).lower()
            broad_keywords = [
                "earbud", "earphone", "headphone", "audio", "sound", "buds",
                "phone", "case", "led", "light", "watch", "charger", "blender",
                "drone", "mouse", "mice", "keyboard", "webcam", "stand", "hub", "bottle"
            ]
            for item in products:
                keywords = set(item.get("keywords", []))
                item_title = item.get("title", "").lower()
                for bk in broad_keywords:
                    if bk in clean_query and (bk in item_title or any(bk in kw for kw in keywords)):
                        scored_items.append((1.0, item))
                        break

        # Fallback 2: Return top products if zero matches
        if not scored_items and products:
            for item in products[:limit]:
                scored_items.append((0.1, item))

        results = []
        for _, item in scored_items[:limit]:
            results.append(self._to_product_model(item))

        return results

    def get_product_details(self, product_id: str) -> Optional[AliExpressProduct]:
        """Fetch single product details by ID."""
        if not product_id or not str(product_id).strip():
            return None

        products = self._load_mock_data()
        for item in products:
            pid = str(item.get("product_id", "") or item.get("id", ""))
            if pid == str(product_id).strip():
                return self._to_product_model(item)
        return None

    def _to_product_model(self, item: dict) -> AliExpressProduct:
        """Convert raw mock dictionary into an AliExpressProduct dataclass."""
        price_val = Decimal(str(item.get("price_value") or item.get("price") or "0.00"))
        orig_val = Decimal(str(item.get("original_value") or item.get("original_price") or price_val))
        currency = str(item.get("currency", "USD"))

        price_obj = AliExpressPrice(
            value=price_val,
            currency=currency,
            original_value=orig_val,
        )

        shipping_cost = Decimal(str(item.get("shipping_cost", "0.00")))
        shipping_method = str(item.get("shipping_method", "Standard Shipping"))
        est_days = int(item.get("estimated_delivery_days", 14))
        shipping_obj = AliExpressShipping(
            method=shipping_method,
            cost=shipping_cost,
            currency=currency,
            estimated_days_min=max(1, est_days - 2),
            estimated_days_max=est_days + 2,
        )

        store_raw = item.get("store", {})
        if isinstance(store_raw, dict) and store_raw:
            store_name = str(store_raw.get("name") or store_raw.get("store_name") or "Official Store")
            store_id = str(store_raw.get("store_id") or store_raw.get("id") or "store_001")
            store_url = str(store_raw.get("url") or f"https://www.aliexpress.com/store/{store_id}")
            store_feedback = float(store_raw.get("positive_feedback_rate") or store_raw.get("rating") or 98.5)
        else:
            store_name = str(item.get("store_name", "Official Store"))
            store_id = str(item.get("store_id", "store_001"))
            store_url = str(item.get("store_url", f"https://www.aliexpress.com/store/{store_id}"))
            store_feedback = float(item.get("positive_feedback_rate", 98.5))

        store_obj = AliExpressStore(
            name=store_name,
            store_id=store_id,
            url=store_url,
            positive_feedback_rate=store_feedback,
        )

        rating_score = float(item.get("rating_score") or item.get("rating") or item.get("store_rating") or 4.5)
        review_count = int(item.get("review_count", 150))
        orders_count = int(item.get("orders_count", 500))
        raw_attrs = item.get("attributes", {})

        product_id = str(item.get("product_id") or item.get("id", ""))
        title = str(item.get("title", ""))
        product_url = str(item.get("product_url", f"https://www.aliexpress.com/item/{product_id}.html"))
        image_url = str(item.get("image_url", ""))
        source = str(item.get("source", "mock"))

        return AliExpressProduct(
            product_id=product_id,
            title=title,
            price=price_obj,
            product_url=product_url,
            source=source,
            image_url=image_url,
            store=store_obj,
            rating_score=rating_score,
            review_count=review_count,
            orders_count=orders_count,
            attributes=raw_attrs,
            shipping_options=[shipping_obj],
        )