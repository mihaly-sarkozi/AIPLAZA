# backend/core/modules/tenant/schema/manager.py
# Feladat: SQLAlchemy alapú tenant schema manager implementáció. Tenant schema létrehozást, törlést és létezés ellenőrzést végez az adatbázisban. Tenant schema infrastruktúra adapter.
# Sárközi Mihály - 2026.05.21

"""SQLAlchemy adapter implementing the TenantSchemaManagerPort.

Responsibility: bridge between the port interface (pure protocol) and the
SQLAlchemy-backed schema service.  This is the only file in the schema
sub-package that depends on the port definition.
"""
from __future__ import annotations

from core.modules.tenant.ports import TenantSchemaManagerPort
from core.modules.tenant.schema.service import (
    create_tenant_schema,
    drop_tenant_schema,
    list_missing_tenant_schema_tables,
    tenant_schema_exists,
)


class SqlAlchemyTenantSchemaManager(TenantSchemaManagerPort):
    def __init__(self, engine) -> None:
        self._engine = engine

    def exists(self, slug: str) -> bool:
        return tenant_schema_exists(self._engine, slug)

    def create(self, slug: str) -> None:
        create_tenant_schema(self._engine, slug)

    def drop(self, slug: str) -> None:
        drop_tenant_schema(self._engine, slug)

    def list_missing_tables(self, slug: str) -> tuple[str, ...]:
        if not self.exists(slug):
            return ()
        return tuple(list_missing_tenant_schema_tables(self._engine, slug))


__all__ = ["SqlAlchemyTenantSchemaManager"]
