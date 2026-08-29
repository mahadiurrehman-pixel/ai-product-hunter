"""
Product Identity Builder.
"""
from typing import Dict, Optional

from services.scoring.normalizer import ProductNormalizer
from services.search.query_parser import QueryParser, SearchIntent
from utils.logger import get_logger

from .models import DataQuality, ProductIdentity
from .model_intelligence import ModelIntelligence
from .attributes import AttributeNormalizer, AttributeConfidence
from .taxonomy import TaxonomyEngine

logger = get_logger(__name__)

_normalizer = ProductNormalizer()
_query_parser = QueryParser()
_model_intelligence = ModelIntelligence()
_attr_normalizer = AttributeNormalizer()
_taxonomy = TaxonomyEngine()


class ProductIdentityBuilder:
    """
    Builds ProductIdentity from raw product data.

    Pipeline:
    1. QueryParser → brand, product_type, basic model, condition
    2. ProductNormalizer → keywords, structured attributes
    3. TaxonomyEngine → role, category_path, compatible_categories
    4. ModelIntelligence → refined model, family, generation, variant
    5. AttributeNormalizer → canonical attributes with rich metadata
    """

    def from_title(
        self,
        title: str,
        source: str = "unknown",
        marketplace: Optional[str] = None,
        extra_attributes: Optional[Dict[str, str]] = None,
    ) -> ProductIdentity:
        if not title or not title.strip():
            return ProductIdentity(
                source=source,
                marketplace=marketplace,
                original_title=title or "",
            )

        # Step 1: QueryParser
        intent = _query_parser.parse(title)

        # Step 2: ProductNormalizer
        normalized = _normalizer.normalize(title)

        # Step 3: Taxonomy resolution
        taxonomy_info = _taxonomy.resolve_type(title)
        if taxonomy_info:
            final_type = taxonomy_info.name
            product_role = taxonomy_info.role
            category_path = taxonomy_info.category_path
            compatible_categories = taxonomy_info.compatible_categories
            is_accessory = taxonomy_info.is_accessory
        else:
            final_type = intent.product_type
            product_role = "unknown"
            category_path = []
            compatible_categories = []
            is_accessory = False

        # Step 4: Model Intelligence
        mi = _model_intelligence.extract(
            title=title,
            product_type=final_type,
            brand=intent.brand or normalized.brand,
        )

        if mi.is_accessory:
            final_model = None
            final_family = None
            is_accessory = True
            if product_role == "unknown":
                product_role = "accessory"
        else:
            final_model = mi.model or intent.model
            final_family = mi.model_family

        # Step 5: Variant
        variant = self._resolve_variant(mi, intent, normalized)

        # Step 6: Attributes
        attributes = dict(extra_attributes or {})
        attributes.update(intent.attributes)
        attributes.update(normalized.attributes)
        attributes = self._normalize_attribute_keys(attributes)

        # Step 6b: Canonical attributes
        title_canonical = _attr_normalizer.normalize_all(
            normalized.attributes,
            source="title",
            confidence=AttributeConfidence.MEDIUM,
        )
        query_canonical = _attr_normalizer.normalize_all(
            intent.attributes,
            source="query",
            confidence=AttributeConfidence.MEDIUM,
        )
        api_canonical = _attr_normalizer.normalize_all(
            extra_attributes or {},
            source="api",
            confidence=AttributeConfidence.HIGH,
        )
        canonical_attrs = _attr_normalizer.merge_with_conflicts(
            title_canonical,
            _attr_normalizer.merge_with_conflicts(
                query_canonical, api_canonical
            ),
        )

        # Step 7: Confidence
        confidence = self._calculate_confidence(
            intent, normalized, mi, variant,
        )

        # Step 8: Quality
        quality = self._classify_quality(confidence, intent, mi)

        return ProductIdentity(
            product_type=final_type,
            product_role=product_role,
            brand=intent.brand or normalized.brand,
            model=final_model,
            model_family=final_family,
            generation=mi.generation,
            variant=variant,
            compatible_models=mi.compatible_models,
            is_accessory=is_accessory,
            condition=intent.condition,
            exclusions=intent.exclusions,
            category_path=category_path,
            compatible_categories=compatible_categories,
            attributes=attributes,
            canonical_attributes=canonical_attrs,
            keywords=normalized.keywords,
            source=source,
            marketplace=marketplace,
            identity_confidence=confidence,
            data_quality=quality,
            original_title=title,
        )

    def from_ebay_listing(self, listing: dict) -> ProductIdentity:
        title = listing.get("title", "")
        marketplace = listing.get("marketplace")
        extra = {}
        if listing.get("product_brand"):
            extra["brand_from_api"] = listing["product_brand"]
        aspects = listing.get("product_aspects")
        if isinstance(aspects, dict):
            for key, values in aspects.items():
                if isinstance(values, list) and values:
                    extra[key.lower()] = str(values[0]).lower()
        return self.from_title(
            title=title, source="ebay",
            marketplace=marketplace, extra_attributes=extra,
        )

    def from_aliexpress_product(self, product) -> ProductIdentity:
        if hasattr(product, "title"):
            title = product.title
            source = getattr(product, "source", "aliexpress")
            attrs = getattr(product, "attributes", {}) or {}
        elif isinstance(product, dict):
            title = product.get("title", "")
            source = product.get("source", "aliexpress")
            attrs = product.get("attributes", {}) or {}
        else:
            title = str(product)
            source = "aliexpress"
            attrs = {}
        return self.from_title(
            title=title, source=source, marketplace=None,
            extra_attributes=attrs if isinstance(attrs, dict) else {},
        )

    def _resolve_variant(self, mi, intent, normalized) -> Optional[str]:
        parts = []
        if mi.variant:
            parts.append(mi.variant)
        storage = (
            normalized.attributes.get("storage")
            or intent.attributes.get("storage")
        )
        if storage and storage.upper() not in (mi.variant or "").upper():
            parts.append(storage.upper())
        memory = (
            normalized.attributes.get("memory")
            or intent.attributes.get("memory")
        )
        if memory and memory.upper() not in (mi.variant or "").upper():
            parts.append(memory.upper())
        return " ".join(parts) if parts else None

    def _normalize_attribute_keys(
        self, attributes: Dict[str, str]
    ) -> Dict[str, str]:
        key_aliases = {
            "colour": "color", "ram": "memory",
            "ram size": "memory", "screen size": "size",
            "display size": "size", "storage capacity": "storage",
        }
        skip_keys = {"brand_from_api"}
        normalized = {}
        for key, value in attributes.items():
            if key in skip_keys:
                continue
            canonical = key_aliases.get(key.lower(), key.lower())
            if canonical not in normalized:
                normalized[canonical] = value
        return normalized

    def _calculate_confidence(
        self, intent, normalized, mi, variant
    ) -> float:
        score = 0.10
        if intent.product_type:
            score += 0.10
        if intent.brand or normalized.brand:
            score += 0.10
        if mi.model:
            score += 0.20
        elif mi.is_accessory and mi.compatible_models:
            score += 0.15
        if mi.model_family:
            score += 0.05
        if mi.generation:
            score += 0.05
        if variant:
            score += 0.05
        if len(normalized.attributes) >= 2:
            score += 0.10
        if intent.condition:
            score += 0.05
        if len(normalized.keywords) >= 3:
            score += 0.05
        return min(1.0, round(score, 3))

    def _classify_quality(self, confidence, intent, mi) -> DataQuality:
        has_model = mi.model or (mi.is_accessory and mi.compatible_models)
        if (
            confidence >= 0.70
            and intent.product_type
            and intent.brand
            and has_model
        ):
            return DataQuality.HIGH
        elif confidence >= 0.40 and intent.product_type:
            return DataQuality.MEDIUM
        else:
            return DataQuality.LOW