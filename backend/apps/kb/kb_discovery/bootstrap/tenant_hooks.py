from __future__ import annotations

from apps.kb.kb_discovery.orm.DiscoveryJob import DiscoveryJob
from apps.kb.kb_discovery.orm.EntityMention import EntityMention
from apps.kb.kb_discovery.orm.KnowledgeEnrichment import KnowledgeEnrichment
from apps.kb.kb_discovery.orm.KnowledgeEntity import KnowledgeEntity
from apps.kb.kb_discovery.orm.KnowledgeKeyword import KnowledgeKeyword
from apps.kb.kb_discovery.orm.KnowledgeRelationship import KnowledgeRelationship
from apps.kb.kb_discovery.orm.KnowledgeScore import KnowledgeScore
from apps.kb.kb_discovery.orm.KnowledgeTopic import KnowledgeTopic
from apps.kb.kb_discovery.orm.ProcessMention import ProcessMention
from apps.kb.kb_discovery.orm.SpatialMention import SpatialMention
from apps.kb.kb_discovery.orm.TemporalMention import TemporalMention
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)


def _install_kb_discovery_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            DiscoveryJob.__table__,
            KnowledgeEntity.__table__,
            EntityMention.__table__,
            KnowledgeEnrichment.__table__,
            KnowledgeKeyword.__table__,
            KnowledgeTopic.__table__,
            TemporalMention.__table__,
            SpatialMention.__table__,
            ProcessMention.__table__,
            KnowledgeRelationship.__table__,
            KnowledgeScore.__table__,
        ),
    )
    run_schema_statements(
        engine,
        slug,
        (
            'ALTER TABLE "{schema}".kb_enrichments ADD COLUMN IF NOT EXISTS knowledge_base_id VARCHAR(64)',
            'ALTER TABLE "{schema}".kb_enrichments ADD COLUMN IF NOT EXISTS training_item_id VARCHAR(64)',
            'ALTER TABLE "{schema}".kb_enrichments ADD COLUMN IF NOT EXISTS preview_text TEXT NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_enrichments ADD COLUMN IF NOT EXISTS content_type_confidence DOUBLE PRECISION NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_enrichments ADD COLUMN IF NOT EXISTS profile_confidence DOUBLE PRECISION NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_enrichments ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT \'{{}}\'::jsonb',
            'ALTER TABLE "{schema}".kb_enrichments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS knowledge_base_id VARCHAR(64)',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS training_item_id VARCHAR(64)',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS normalized_term VARCHAR(256) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS display_term VARCHAR(256) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS language_code VARCHAR(8)',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS source VARCHAR(64) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS extractor_version VARCHAR(32) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS start_offset INTEGER',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS end_offset INTEGER',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT \'{{}}\'::jsonb',
            'ALTER TABLE "{schema}".kb_keywords ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_topics ADD COLUMN IF NOT EXISTS knowledge_base_id VARCHAR(64)',
            'ALTER TABLE "{schema}".kb_topics ADD COLUMN IF NOT EXISTS training_item_id VARCHAR(64)',
            'ALTER TABLE "{schema}".kb_topics ADD COLUMN IF NOT EXISTS display_name VARCHAR(256) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_topics ADD COLUMN IF NOT EXISTS normalized_topic VARCHAR(128) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_topics ADD COLUMN IF NOT EXISTS language_code VARCHAR(8)',
            'ALTER TABLE "{schema}".kb_topics ADD COLUMN IF NOT EXISTS score DOUBLE PRECISION NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_topics ADD COLUMN IF NOT EXISTS source VARCHAR(64) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_topics ADD COLUMN IF NOT EXISTS taxonomy_version VARCHAR(32) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_topics ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT \'{{}}\'::jsonb',
            'ALTER TABLE "{schema}".kb_topics ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_temporal_mentions ADD COLUMN IF NOT EXISTS knowledge_base_id VARCHAR(64)',
            'ALTER TABLE "{schema}".kb_temporal_mentions ADD COLUMN IF NOT EXISTS training_item_id VARCHAR(64)',
            'ALTER TABLE "{schema}".kb_temporal_mentions ADD COLUMN IF NOT EXISTS start_offset INTEGER',
            'ALTER TABLE "{schema}".kb_temporal_mentions ADD COLUMN IF NOT EXISTS end_offset INTEGER',
            'ALTER TABLE "{schema}".kb_temporal_mentions ADD COLUMN IF NOT EXISTS language_code VARCHAR(8)',
            'ALTER TABLE "{schema}".kb_temporal_mentions ADD COLUMN IF NOT EXISTS recognizer_name VARCHAR(64) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_temporal_mentions ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT \'{{}}\'::jsonb',
            'ALTER TABLE "{schema}".kb_temporal_mentions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_spatial_mentions ADD COLUMN IF NOT EXISTS knowledge_base_id VARCHAR(64)',
            'ALTER TABLE "{schema}".kb_spatial_mentions ADD COLUMN IF NOT EXISTS training_item_id VARCHAR(64)',
            'ALTER TABLE "{schema}".kb_spatial_mentions ADD COLUMN IF NOT EXISTS start_offset INTEGER',
            'ALTER TABLE "{schema}".kb_spatial_mentions ADD COLUMN IF NOT EXISTS end_offset INTEGER',
            'ALTER TABLE "{schema}".kb_spatial_mentions ADD COLUMN IF NOT EXISTS language_code VARCHAR(8)',
            'ALTER TABLE "{schema}".kb_spatial_mentions ADD COLUMN IF NOT EXISTS recognizer_name VARCHAR(64) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_spatial_mentions ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT \'{{}}\'::jsonb',
            'ALTER TABLE "{schema}".kb_spatial_mentions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_relationships ADD COLUMN IF NOT EXISTS training_item_id VARCHAR(64)',
            'ALTER TABLE "{schema}".kb_relationships ADD COLUMN IF NOT EXISTS weight DOUBLE PRECISION NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_relationships ADD COLUMN IF NOT EXISTS evidence_chunk_ids JSONB NOT NULL DEFAULT \'[]\'::jsonb',
            'ALTER TABLE "{schema}".kb_relationships ADD COLUMN IF NOT EXISTS evidence_text TEXT NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_relationships ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT \'{{}}\'::jsonb',
            'ALTER TABLE "{schema}".kb_relationships ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()',
        ),
    )


def register_kb_discovery_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_discovery",
                revision="kb.discovery.schema.v7",
                install=_install_kb_discovery_schema,
                table_names=(
                    "kb_discovery_jobs",
                    "kb_entities",
                    "kb_entity_mentions",
                    "kb_enrichments",
                    "kb_keywords",
                    "kb_topics",
                    "kb_temporal_mentions",
                    "kb_spatial_mentions",
                    "kb_process_mentions",
                    "kb_relationships",
                    "kb_scores",
                ),
            )
        ]
    )


__all__ = ["register_kb_discovery_tenant_hooks"]
