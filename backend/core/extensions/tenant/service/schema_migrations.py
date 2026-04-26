# Backward-compat re-export – implementation moved to service/schema/migrations.py
from core.extensions.tenant.schema.migrations import (  # noqa: F401
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
