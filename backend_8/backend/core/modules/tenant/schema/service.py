# backend/core/modules/tenant/schema/service.py
# Feladat: Tenant schema service helper függvényeket tartalmaz. Tenant schema létrehozást, upgrade-et, szinkronizációt, hiányzó táblák listázását és tenant slug lekérdezést végez schema manager és hook registry fölött. Tenant schema orchestration service.
# Sárközi Mihály - 2026.05.21

"""Tenant schema lifecycle orchestration.

Responsibility: orchestrate tenant schema upgrade, drop, existence check and
sync.  Delegates DDL execution to ``ddl``, migration tracking to
``migrations``, public schema setup to ``public``, and hook iteration to
``hooks``.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.modules.tenant.schema.ddl import _safe_slug
from core.modules.tenant.schema.hooks import (
    list_tenant_schema_hooks,
    list_tenant_schema_table_names,
    register_manifest_tenant_schema_hooks,  # noqa: F401 – re-exported for callers
    register_tenant_schema_hooks,            # noqa: F401 – re-exported for callers
    reset_tenant_schema_hooks,               # noqa: F401 – re-exported for callers
    TenantSchemaHook,                        # noqa: F401 – re-exported for callers
    tenant_migration_revision,
)
from core.modules.tenant.schema.migrations import (
    ensure_tenant_migration_table,
    list_applied_tenant_migrations,
    PublicSchemaMigration,  # noqa: F401 – backward compat
    record_tenant_migration,
)
from core.modules.tenant.schema.public import upgrade_public_schema  # noqa: F401

# Re-export DDL helpers so existing callers don't need to change their imports.
from core.modules.tenant.schema.ddl import install_schema_tables, run_schema_statements  # noqa: F401


def upgrade_tenant_schema(engine: Engine, slug: str) -> None:
    """Apply all pending tenant-schema migration hooks for *slug* idempotently."""
    safe_slug = _safe_slug(slug)
    ensure_tenant_migration_table(engine, safe_slug)
    applied = list_applied_tenant_migrations(engine, safe_slug)
    for hook in list_tenant_schema_hooks():
        revision = tenant_migration_revision(hook)
        if revision in applied:
            continue
        hook.install(engine, safe_slug)
        record_tenant_migration(engine, safe_slug, hook)
        applied.add(revision)


def drop_tenant_schema(engine: Engine, slug: str) -> None:
    safe_slug = _safe_slug(slug)
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{safe_slug}" CASCADE'))
        commit = getattr(conn, "commit", None)
        if callable(commit):
            commit()


def create_tenant_schema(engine: Engine, slug: str) -> None:
    """Create or upgrade the tenant schema via the official migration chain."""
    upgrade_tenant_schema(engine, slug)


def tenant_schema_exists(engine: Engine, slug: str) -> bool:
    safe_slug = _safe_slug(slug)
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT 1
                FROM information_schema.schemata
                WHERE schema_name = :schema_name
            """),
            {"schema_name": safe_slug},
        ).first()
    return row is not None


def list_missing_tenant_schema_tables(engine: Engine, slug: str) -> list[str]:
    safe_slug = _safe_slug(slug)
    table_names = list_tenant_schema_table_names()
    if not table_names:
        return []
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = :schema_name
            """),
            {"schema_name": safe_slug},
        ).fetchall()
    existing = {row[0] for row in rows}
    return [name for name in table_names if name not in existing]


def list_tenant_slugs(engine: Engine) -> list[str]:
    """Return all known tenant slugs from public.tenants."""
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT slug FROM public.tenants")).fetchall()
    return [row[0] for row in rows]


def sync_existing_tenant_schemas(engine: Engine) -> None:
    """Run public migrations, then apply pending hooks for every known tenant."""
    upgrade_public_schema(engine)
    for slug in list_tenant_slugs(engine):
        try:
            _safe_slug(slug)
        except ValueError:
            continue
        upgrade_tenant_schema(engine, slug)


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
