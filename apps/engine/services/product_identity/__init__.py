"""Product Identity Layer."""
from .models import ProductIdentity, DataQuality
from .builder import ProductIdentityBuilder
from .model_intelligence import ModelIntelligence, ModelIntelligenceResult
from .attributes import (
    AttributeNormalizer, CanonicalAttribute,
    AttributeConfidence, AttributeStatus,
)
from .units import UnitConverter, UnitConversionResult
from .evidence import (
    Evidence, EvidenceSet, EvidenceType,
    EvidenceStrength, ConflictSeverity,
)
from .conflict_detector import ConflictDetector
from .quality import (
    ConfidenceLevel, FieldConfidence,
    DataQualityReport, DataQualityAnalyzer,
    QualityFlag, DataQualityScore, DQSLevel,
)
from .taxonomy import TaxonomyEngine, ProductTypeInfo

__all__ = [
    "ProductIdentity", "DataQuality", "ProductIdentityBuilder",
    "ModelIntelligence", "ModelIntelligenceResult",
    "AttributeNormalizer", "CanonicalAttribute",
    "AttributeConfidence", "AttributeStatus",
    "UnitConverter", "UnitConversionResult",
    "Evidence", "EvidenceSet", "EvidenceType",
    "EvidenceStrength", "ConflictSeverity",
    "ConflictDetector",
    "ConfidenceLevel", "FieldConfidence",
    "DataQualityReport", "DataQualityAnalyzer",
    "QualityFlag", "DataQualityScore", "DQSLevel",
    "TaxonomyEngine", "ProductTypeInfo",
]