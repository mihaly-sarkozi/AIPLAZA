from __future__ import annotations

from core.extensions.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)
from core.platform.settings.models import SettingsORM


def _install_settings_schema(engine, slug: str) -> None:
    install_schema_tables(engine, slug, (SettingsORM.__table__,))
    run_schema_statements(
        engine,
        slug,
        (
            'ALTER TABLE "{schema}".settings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".settings ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".settings ADD COLUMN IF NOT EXISTS updated_by INTEGER',
        ),
    )


def register_settings_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="settings",
                install=_install_settings_schema,
                table_names=("settings",),
            )
        ]
    )


__all__ = ["register_settings_tenant_hooks"]
