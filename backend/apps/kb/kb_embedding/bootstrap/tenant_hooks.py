from __future__ import annotations

from apps.kb.kb_embedding.orm.EmbeddingJob import EmbeddingJob
from apps.kb.kb_embedding.orm.KnowledgeEmbedding import KnowledgeEmbedding
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
)


def _install_kb_embedding_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            EmbeddingJob.__table__,
            KnowledgeEmbedding.__table__,
        ),
    )


def register_kb_embedding_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_embedding",
                revision="kb.embedding.schema.v1",
                install=_install_kb_embedding_schema,
                table_names=(
                    "kb_embedding_jobs",
                    "kb_embeddings",
                ),
            )
        ]
    )


__all__ = ["register_kb_embedding_tenant_hooks"]
