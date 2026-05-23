# backend/core/modules/brand/tenant_hooks.py
# Feladat: A brand modul tenant schema telepítési hookját regisztrálja. Létrehozza és kompatibilisen frissíti a brand_settings táblát minden tenant sémában, beleértve audit mezőket és public_enabled kapcsolót. Brand tenant provisioning adapter, amelyet a BrandCoreModule köt be.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.tenant.service import (
    TenantSchemaHook,
    install_schema_tables,
    register_tenant_schema_hooks,
    run_schema_statements,
)
from core.modules.brand.persistence.brand_settings_orm import BrandSettingsORM


def _install_brand_schema(engine, slug: str) -> None:
    install_schema_tables(engine, slug, (BrandSettingsORM.__table__,))
    run_schema_statements(
        engine,
        slug,
        (
            'ALTER TABLE "{schema}".brand_settings ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".brand_settings ADD COLUMN IF NOT EXISTS created_by INTEGER',
            'ALTER TABLE "{schema}".brand_settings ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()',
            'ALTER TABLE "{schema}".brand_settings ADD COLUMN IF NOT EXISTS updated_by INTEGER',
            'ALTER TABLE "{schema}".brand_settings ADD COLUMN IF NOT EXISTS public_enabled BOOLEAN DEFAULT TRUE',
        ),
    )


def register_brand_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="brand_settings",
                install=_install_brand_schema,
                table_names=("brand_settings",),
            )
        ]
    )
