# backend/core/modules/tenant/service/schema_migrations.py
# Feladat: Kompatibilitási importútvonal a tenant schema migration contractokhoz. A canonical implementáció a schema/migrations.py alatt él, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.schema.migrations import (  # noqa: F401
    PublicSchemaMigration,
    ensure_public_migration_table,
    ensure_tenant_migration_table,
    ensure_tenant_schema,
    list_applied_public_migrations,
    list_applied_tenant_migrations,
    record_public_migration,
    record_tenant_migration,
)

__all__ = [
    "PublicSchemaMigration",
    "ensure_public_migration_table",
    "ensure_tenant_migration_table",
    "ensure_tenant_schema",
    "list_applied_public_migrations",
    "list_applied_tenant_migrations",
    "record_public_migration",
    "record_tenant_migration",
]
