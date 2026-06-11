from __future__ import annotations

# backend/apps/kb/kb_crud/bootstrap/tenant_hooks.py
# Feladat: Tudástár CRUD táblák (knowledge_bases, kb_user_permission) létrehozása telepítésnél.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_crud.orm.KnowledgeBaseORM import KnowledgeBaseORM
from apps.kb.kb_crud.orm.KnowledgeBasePermissionORM import KnowledgeBasePermissionORM
from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)


def _install_kb_crud_schema(engine, slug: str) -> None:
    install_schema_tables(
        engine,
        slug,
        (
            KnowledgeBaseORM.__table__,
            KnowledgeBasePermissionORM.__table__,
        ),
    )
    run_schema_statements(
        engine,
        slug,
        (
            'ALTER TABLE "{schema}".knowledge_bases ALTER COLUMN name TYPE VARCHAR(200)',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS updated_by INTEGER',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS deleted_display_name VARCHAR(200)',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS deleted_training_char_count BIGINT NOT NULL DEFAULT 0',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS pii_depersonalization_enabled BOOLEAN NOT NULL DEFAULT TRUE',
            'ALTER TABLE "{schema}".knowledge_bases ADD COLUMN IF NOT EXISTS public_enabled BOOLEAN NOT NULL DEFAULT FALSE',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()',
            'ALTER TABLE "{schema}".kb_user_permission ADD COLUMN IF NOT EXISTS updated_by INTEGER',
        ),
    )


def register_kb_crud_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="kb_crud",
                revision="kb.crud.schema.v1.knowledge_bases_ownership",
                install=_install_kb_crud_schema,
                table_names=(
                    "knowledge_bases",
                    "kb_user_permission",
                ),
            )
        ]
    )


__all__ = ["register_kb_crud_tenant_hooks"]
