from __future__ import annotations

# backend/apps/kb/kb_understanding/bootstrap/tenant_hooks.py
# Feladat: Megértési modul tenant tábláinak telepítése.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.orm.ExtractedContent import ExtractedContent
from apps.kb.kb_understanding.orm.KnowledgeChunk import KnowledgeChunk
from apps.kb.kb_understanding.orm.KnowledgeEmbedding import KnowledgeEmbedding
from apps.kb.kb_understanding.orm.KnowledgeEnrichment import KnowledgeEnrichment
from apps.kb.kb_understanding.orm.KnowledgeEntity import KnowledgeEntity
from apps.kb.kb_understanding.orm.KnowledgeRelationship import KnowledgeRelationship
from apps.kb.kb_understanding.orm.KnowledgeScore import KnowledgeScore
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
            NormalizedContent.__table__,
            StructuredBlock.__table__,
            KnowledgeChunk.__table__,
            KnowledgeEntity.__table__,
            KnowledgeRelationship.__table__,
            KnowledgeEnrichment.__table__,
            KnowledgeEmbedding.__table__,
            KnowledgeScore.__table__,
        ),
    )


def register_kb_understanding_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_understanding",
                revision="kb.understanding.schema.v1",
                install=_install_kb_understanding_schema,
                table_names=(
                    "kb_understanding_jobs",
                    "kb_understanding_step_runs",
                    "kb_extracted_content",
                    "kb_normalized_content",
                    "kb_structured_blocks",
                    "kb_chunks",
                    "kb_entities",
                    "kb_relationships",
                    "kb_enrichments",
                    "kb_embeddings",
                    "kb_scores",
                ),
            )
        ]
    )


__all__ = ["register_kb_understanding_tenant_hooks"]
