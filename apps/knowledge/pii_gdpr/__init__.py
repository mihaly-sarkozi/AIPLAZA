# apps/knowledge/pii_gdpr/__init__.py
"""
Multilingual PII/GDPR detection and sanitization pipeline for knowledge-base ingestion.
"""
from apps.knowledge.pii_gdpr.enums import (
    EntityType,
    RecommendedAction,
    RiskClass,
    PolicyMode,
    Language,
    EmailClassification,
)
from apps.knowledge.pii_gdpr.models import (
    DetectionResult,
    DetectionSummary,
    SanitizationResult,
    PolicyDecision,
    AnalyzerConfig,
    PolicyConfig,
)
from apps.knowledge.pii_gdpr.pipeline.ingestion_pipeline import IngestionPipeline

__all__ = [
    "EntityType",
    "RecommendedAction",
    "RiskClass",
    "PolicyMode",
    "Language",
    "EmailClassification",
    "DetectionResult",
    "DetectionSummary",
    "SanitizationResult",
    "PolicyDecision",
    "AnalyzerConfig",
    "PolicyConfig",
    "IngestionPipeline",
]
