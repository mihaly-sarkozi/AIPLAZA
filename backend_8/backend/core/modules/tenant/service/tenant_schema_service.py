# backend/core/modules/tenant/service/tenant_schema_service.py
# Feladat: Kompatibilitási importútvonal a tenant schema service helper függvényekhez. A canonical implementáció a schema/service.py alatt él, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.schema.service import (  # noqa: F401
    PublicSchemaMigration,
    TenantSchemaHook,
    create_tenant_schema,
    drop_tenant_schema,
    install_schema_tables,
    list_missing_tenant_schema_tables,
    list_tenant_schema_hooks,
    list_tenant_schema_table_names,
    list_tenant_slugs,
    register_manifest_tenant_schema_hooks,
    register_tenant_schema_hooks,
    reset_tenant_schema_hooks,
    run_schema_statements,
    sync_existing_tenant_schemas,
    tenant_schema_exists,
    upgrade_public_schema,
    upgrade_tenant_schema,
)

__all__ = [
    "PublicSchemaMigration",
    "TenantSchemaHook",
    "create_tenant_schema",
    "drop_tenant_schema",
    "install_schema_tables",
    "list_missing_tenant_schema_tables",
    "list_tenant_schema_hooks",
    "list_tenant_schema_table_names",
    "list_tenant_slugs",
    "register_manifest_tenant_schema_hooks",
    "register_tenant_schema_hooks",
    "reset_tenant_schema_hooks",
    "run_schema_statements",
    "sync_existing_tenant_schemas",
    "tenant_schema_exists",
    "upgrade_public_schema",
    "upgrade_tenant_schema",
]
