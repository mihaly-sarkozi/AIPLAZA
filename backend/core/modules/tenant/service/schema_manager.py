# backend/core/modules/tenant/service/schema_manager.py
# Feladat: A régi tenant service importútvonal schema_manager kompatibilitási fájlja. A canonical implementáció már a tenant schema, signup, provisioning, tokens vagy slug csomagok alatt él. Backward-compat shim a meglévő importokhoz.
# Sárközi Mihály - 2026.05.21

from core.modules.tenant.schema.manager import SqlAlchemyTenantSchemaManager  # noqa: F401

__all__ = ["SqlAlchemyTenantSchemaManager"]
