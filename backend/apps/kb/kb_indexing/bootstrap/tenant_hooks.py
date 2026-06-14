from __future__ import annotations

from apps.kb.kb_indexing.orm.IndexRebuild import IndexRebuild
from apps.kb.kb_indexing.orm.IndexVerification import IndexVerification
from apps.kb.kb_indexing.orm.IndexVerificationItem import IndexVerificationItem
from apps.kb.kb_indexing.orm.IndexedChunk import IndexedChunk
from apps.kb.kb_indexing.orm.IndexingJob import IndexingJob
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
)


def _install_kb_indexing_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            IndexingJob.__table__,
            IndexedChunk.__table__,
            IndexVerification.__table__,
            IndexVerificationItem.__table__,
            IndexRebuild.__table__,
        ),
    )


def register_kb_indexing_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_indexing",
                revision="kb.indexing.schema.v3",
                install=_install_kb_indexing_schema,
                table_names=(
                    "kb_indexing_jobs",
                    "kb_indexed_chunks",
                    "kb_index_verifications",
                    "kb_index_verification_items",
                    "kb_index_rebuilds",
                ),
            )
        ]
    )


__all__ = ["register_kb_indexing_tenant_hooks"]
