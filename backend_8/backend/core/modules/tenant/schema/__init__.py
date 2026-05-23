# backend/core/modules/tenant/schema/__init__.py
# Feladat: A tenant schema csomag exportfelülete. DDL, hook registry, schema manager, public migration és tenant schema service helper funkciókat ad tovább canonical importpontként. Tenant schema management belépési pont.
# Sárközi Mihály - 2026.05.21

"""Tenant schema management sub-package.

Sub-modules:
- ``ddl``        – low-level DDL primitives (CREATE TABLE, raw SQL)
- ``migrations`` – migration-state tracking (bookkeeping tables)
- ``public``     – public schema DDL and upgrade orchestration
- ``hooks``      – tenant schema hook registry
- ``service``    – tenant schema lifecycle orchestration
- ``manager``    – SQLAlchemy adapter implementing TenantSchemaManagerPort
"""
from __future__ import annotations

import importlib

__all__ = [
    "PublicSchemaMigration",
    "SqlAlchemyTenantSchemaManager",
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
    "tenant_migration_revision",
    "tenant_schema_exists",
    "upgrade_public_schema",
    "upgrade_tenant_schema",
]

_LAZY: dict[str, tuple[str, str]] = {
    "PublicSchemaMigration": ("core.modules.tenant.schema.migrations", "PublicSchemaMigration"),
    "SqlAlchemyTenantSchemaManager": ("core.modules.tenant.schema.manager", "SqlAlchemyTenantSchemaManager"),
    "TenantSchemaHook": ("core.modules.tenant.schema.hooks", "TenantSchemaHook"),
    "tenant_migration_revision": ("core.modules.tenant.schema.hooks", "tenant_migration_revision"),
    "register_tenant_schema_hooks": ("core.modules.tenant.schema.hooks", "register_tenant_schema_hooks"),
    "register_manifest_tenant_schema_hooks": ("core.modules.tenant.schema.hooks", "register_manifest_tenant_schema_hooks"),
    "reset_tenant_schema_hooks": ("core.modules.tenant.schema.hooks", "reset_tenant_schema_hooks"),
    "list_tenant_schema_hooks": ("core.modules.tenant.schema.hooks", "list_tenant_schema_hooks"),
    "list_tenant_schema_table_names": ("core.modules.tenant.schema.hooks", "list_tenant_schema_table_names"),
    "install_schema_tables": ("core.modules.tenant.schema.ddl", "install_schema_tables"),
    "run_schema_statements": ("core.modules.tenant.schema.ddl", "run_schema_statements"),
    "upgrade_public_schema": ("core.modules.tenant.schema.public", "upgrade_public_schema"),
    "upgrade_tenant_schema": ("core.modules.tenant.schema.service", "upgrade_tenant_schema"),
    "drop_tenant_schema": ("core.modules.tenant.schema.service", "drop_tenant_schema"),
    "create_tenant_schema": ("core.modules.tenant.schema.service", "create_tenant_schema"),
    "tenant_schema_exists": ("core.modules.tenant.schema.service", "tenant_schema_exists"),
    "list_missing_tenant_schema_tables": ("core.modules.tenant.schema.service", "list_missing_tenant_schema_tables"),
    "list_tenant_slugs": ("core.modules.tenant.schema.service", "list_tenant_slugs"),
    "sync_existing_tenant_schemas": ("core.modules.tenant.schema.service", "sync_existing_tenant_schemas"),
}


def __getattr__(name: str):
    if name in _LAZY:
        module_path, attr = _LAZY[name]
        return getattr(importlib.import_module(module_path), attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
