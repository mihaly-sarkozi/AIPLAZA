# Backward-compat re-export – implementation moved to service/schema/hooks.py
from core.extensions.tenant.schema.hooks import (  # noqa: F401
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
