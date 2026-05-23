# backend/core/modules/settings/tenant_hooks.py
# Feladat: A settings tenant schema hook regisztrációját tartalmazza. Tenant schema létrehozáskor telepíti a `settings` táblát, és idempotens ALTER statementekkel biztosítja az audit mezők meglétét. Tenant provisioning adapter a settings modul perzisztenciájához.
# Sárközi Mihály - 2026.05.21
from __future__ import annotations

from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)
from core.modules.settings.models.settings_orm import SettingsORM


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
