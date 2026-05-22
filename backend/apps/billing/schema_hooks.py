# backend/apps/billing/schema_hooks.py
# Feladat: Billing tenant schema hook regisztrációs pont. Jelenleg no-op tenant schema installt ad, mert a billing adatok public schema táblákban élnek, de a tenant lifecycle hook contractban láthatóvá teszi az appot. Program-specifikus schema hook adapter.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from core.modules.tenant.service import TenantSchemaHook, install_schema_tables, register_tenant_schema_hooks, run_schema_statements


def _install_billing_tenant_schema(engine, slug: str) -> None:
    install_schema_tables(engine, slug, ())
    run_schema_statements(engine, slug, ())


def register_billing_tenant_hooks() -> None:
    register_tenant_schema_hooks(
        [
            TenantSchemaHook(
                name="billing_noop",
                install=_install_billing_tenant_schema,
                table_names=(),
            )
        ]
    )


__all__ = ["register_billing_tenant_hooks"]
