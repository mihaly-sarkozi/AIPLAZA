from __future__ import annotations

from apps.kb.kb_understanding.orm.ExtractedContent import ExtractedContent
from apps.kb.kb_understanding.orm.ExtractedContentPart import ExtractedContentPart
from apps.kb.kb_understanding.orm.KnowledgeChunk import KnowledgeChunk
from apps.kb.kb_understanding.orm.NormalizedContent import NormalizedContent
from apps.kb.kb_understanding.orm.NormalizedContentPart import NormalizedContentPart
from apps.kb.kb_understanding.orm.UnderstandingJob import UnderstandingJob
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)


def _install_kb_understanding_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            UnderstandingJob.__table__,
            ExtractedContent.__table__,
            ExtractedContentPart.__table__,
            NormalizedContent.__table__,
            NormalizedContentPart.__table__,
            KnowledgeChunk.__table__,
        ),
    )
    run_schema_statements(
        engine,
        slug,
        (
            'ALTER TABLE "{schema}".kb_normalized_content ADD COLUMN IF NOT EXISTS part_map JSONB NOT NULL DEFAULT \'[]\'::jsonb',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS raw_ref VARCHAR(1024)',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS mime_type VARCHAR(255)',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS extractor_name VARCHAR(64) NOT NULL DEFAULT \'\'',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS extractor_version VARCHAR(32) NOT NULL DEFAULT \'1.0\'',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS total_pages INTEGER',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS total_chars INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS text_parts_count INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS table_parts_count INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS ocr_text_parts_count INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS ocr_empty_parts_count INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS ocr_failed_parts_count INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT \'completed\'',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT \'{{}}\'::jsonb',
            'ALTER TABLE "{schema}".kb_extracted_content ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_normalized_content ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT \'processing\'',
            'ALTER TABLE "{schema}".kb_normalized_content ADD COLUMN IF NOT EXISTS part_count INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_normalized_content ADD COLUMN IF NOT EXISTS total_chars INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".kb_normalized_content ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT \'{{}}\'::jsonb',
            'ALTER TABLE "{schema}".kb_normalized_content ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT NOW()',
            # v9: structure layer removed — drop deprecated table if present
            'DROP TABLE IF EXISTS "{schema}".kb_structured_blocks',
            'ALTER TABLE "{schema}".kb_chunks ADD COLUMN IF NOT EXISTS language_code VARCHAR(16)',
            'ALTER TABLE "{schema}".kb_chunks ADD COLUMN IF NOT EXISTS language_confidence DOUBLE PRECISION',
            'ALTER TABLE "{schema}".kb_chunks ADD COLUMN IF NOT EXISTS language_detected_by VARCHAR(64)',
        ),
    )


def register_kb_understanding_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_understanding",
                revision="kb.understanding.schema.v11",
                install=_install_kb_understanding_schema,
                table_names=(
                    "kb_understanding_jobs",
                    "kb_extracted_content",
                    "kb_extracted_content_parts",
                    "kb_normalized_content",
                    "kb_normalized_content_parts",
                    "kb_chunks",
                ),
            )
        ]
    )


__all__ = ["register_kb_understanding_tenant_hooks"]
