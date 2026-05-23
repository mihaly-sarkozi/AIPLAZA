# backend/core/modules/tenant/service/tenant_schema_hooks_registry.py
# Feladat: Kompatibilitási importútvonal a tenant schema hook registryhez. A canonical implementáció a schema/hooks.py alatt él, ez a fájl régi service importokat tart életben. Backward-compat shim.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.schema.hooks import (  # noqa: F401
    TenantSchemaHook,
    list_tenant_schema_hooks,
    list_tenant_schema_table_names,
    register_manifest_tenant_schema_hooks,
    register_tenant_schema_hooks,
    reset_tenant_schema_hooks,
    tenant_migration_revision,
)

__all__ = [
    "TenantSchemaHook",
    "list_tenant_schema_hooks",
    "list_tenant_schema_table_names",
    "register_manifest_tenant_schema_hooks",
    "register_tenant_schema_hooks",
    "reset_tenant_schema_hooks",
    "tenant_migration_revision",
]
