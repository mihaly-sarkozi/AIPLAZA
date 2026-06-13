from __future__ import annotations

from apps.kb.kb_understanding.orm.ExtractedContent import ExtractedContent
from apps.kb.kb_understanding.orm.ExtractedContentPart import ExtractedContentPart
from apps.kb.kb_understanding.orm.KnowledgeChunk import KnowledgeChunk
from apps.kb.kb_understanding.orm.KnowledgeEmbedding import KnowledgeEmbedding
from apps.kb.kb_understanding.orm.NormalizedContent import NormalizedContent
from apps.kb.kb_understanding.orm.StructuredBlock import StructuredBlock
from apps.kb.kb_understanding.orm.UnderstandingJob import UnderstandingJob
from apps.kb.kb_understanding.orm.UnderstandingStepRun import UnderstandingStepRun
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
)


def _install_kb_understanding_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            UnderstandingJob.__table__,
            UnderstandingStepRun.__table__,
            ExtractedContent.__table__,
            ExtractedContentPart.__table__,
            NormalizedContent.__table__,
            StructuredBlock.__table__,
            KnowledgeChunk.__table__,
            KnowledgeEmbedding.__table__,
        ),
    )


def register_kb_understanding_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_understanding",
                revision="kb.understanding.schema.v3",
                install=_install_kb_understanding_schema,
                table_names=(
                    "kb_understanding_jobs",
                    "kb_understanding_step_runs",
                    "kb_extracted_content",
                    "kb_extracted_content_parts",
                    "kb_normalized_content",
                    "kb_structured_blocks",
                    "kb_chunks",
                    "kb_embeddings",
                ),
            )
        ]
    )


__all__ = ["register_kb_understanding_tenant_hooks"]
