# Ez a fájl a(z) apps/features/knowledge/pii_gdpr/pipeline csomag exportjait és inicializálási pontjait fogja össze.
from apps.knowledge.pii_gdpr.pipeline.multilingual_analyzer import MultilingualAnalyzer
from apps.knowledge.pii_gdpr.pipeline.ingestion_pipeline import IngestionPipeline

__all__ = ["MultilingualAnalyzer", "IngestionPipeline"]
