from __future__ import annotations

from apps.kb.kb_processing.orm.ProcessingEvent import ProcessingEvent
from apps.kb.kb_processing.orm.ProcessingIssue import ProcessingIssue
from apps.kb.kb_processing.orm.ProcessingMetrics import ProcessingMetrics
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
)


def _install_kb_processing_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            ProcessingEvent.__table__,
            ProcessingIssue.__table__,
            ProcessingMetrics.__table__,
        ),
    )


def register_kb_processing_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_processing",
                revision="kb.processing.schema.v1",
                install=_install_kb_processing_schema,
                table_names=(
                    "kb_processing_events",
                    "kb_processing_issues",
                    "kb_processing_metrics",
                ),
            )
        ]
    )


__all__ = ["register_kb_processing_tenant_hooks"]
