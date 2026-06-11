from __future__ import annotations

# backend/apps/kb/kb_ingest/bootstrap/tenant_hooks.py
# Feladat: Training táblák létrehozása telepítésnél.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_ingest.orm.TrainingBatch import TrainingBatch
from apps.kb.kb_ingest.orm.TrainingEvent import TrainingEvent
from apps.kb.kb_ingest.orm.TrainingItem import TrainingItem
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)


def _install_kb_ingest_schema(engine, slug: str) -> None:
    # A korábbi kb_training_* táblák átnevezése (meglévő tenant sémák, adatmegőrzéssel);
    # új sémánál no-op, a táblákat az install_schema_tables hozza létre kb_ingest_* néven.
    run_schema_statements(
        engine,
        slug,
        (
            'ALTER TABLE IF EXISTS "{schema}".kb_training_batches RENAME TO kb_ingest_batches',
            'ALTER TABLE IF EXISTS "{schema}".kb_training_items RENAME TO kb_ingest_items',
            'ALTER TABLE IF EXISTS "{schema}".kb_training_events RENAME TO kb_ingest_events',
        ),
    )
    install_schema_tables(
        engine,
        slug,
        (
            TrainingBatch.__table__,
            TrainingItem.__table__,
            TrainingEvent.__table__,
        ),
    )
    run_schema_statements(
        engine,
        slug,
        ('ALTER TABLE "{schema}".kb_ingest_items DROP COLUMN IF EXISTS idempotency_key',),
    )


def register_kb_ingest_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_ingest",
                revision="kb.ingest.schema.v3.rename_training_tables",
                install=_install_kb_ingest_schema,
                table_names=(
                    "kb_ingest_batches",
                    "kb_ingest_items",
                    "kb_ingest_events",
                ),
            )
        ]
    )


__all__ = ["register_kb_ingest_tenant_hooks"]
