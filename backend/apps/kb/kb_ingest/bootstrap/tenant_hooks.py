from __future__ import annotations

# backend/apps/kb/kb_training/bootstrap/tenant_hooks.py
# Feladat: Training táblák létrehozása telepítésnél.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_training.orm.TrainingBatch import TrainingBatch
from apps.kb.kb_training.orm.TrainingEvent import TrainingEvent
from apps.kb.kb_training.orm.TrainingItem import TrainingItem
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)


def _install_kb_training_schema(engine, slug: str) -> None:
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
        ('ALTER TABLE "{schema}".kb_training_items DROP COLUMN IF EXISTS idempotency_key',),
    )


def register_kb_training_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_training",
                revision="kb.training.schema.v2.content_hash_no_idempotency",
                install=_install_kb_training_schema,
                table_names=(
                    "kb_training_batches",
                    "kb_training_items",
                    "kb_training_events",
                ),
            )
        ]
    )


__all__ = ["register_kb_training_tenant_hooks"]
