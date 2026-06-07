from __future__ import annotations

from apps.kb.kb_reading.orm.ReadingBatch import ReadingBatch
from apps.kb.kb_reading.orm.ReadingEvent import ReadingEvent
from apps.kb.kb_reading.orm.ReadingItem import ReadingItem
from core.modules.tenant.service import TenantSchemaHook, install_schema_tables, register_tenant_schema_hooks


def _install_kb_reading_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            ReadingBatch.__table__,
            ReadingItem.__table__,
            ReadingEvent.__table__,
        ),
    )


def register_kb_reading_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_reading",
                revision="kb.reading.schema.v1.initial",
                install=_install_kb_reading_schema,
                table_names=(
                    "kb_reading_batches",
                    "kb_reading_items",
                    "kb_reading_events",
                ),
            )
        ]
    )


__all__ = ["register_kb_reading_tenant_hooks"]
