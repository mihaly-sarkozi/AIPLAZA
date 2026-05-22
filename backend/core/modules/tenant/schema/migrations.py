# backend/core/modules/tenant/schema/migrations.py
# Feladat: Tenant schema migrációs típusokat és helper függvényeket tartalmaz. PublicSchemaMigration contractot és táblanév gyűjtést ad a schema service/migration folyamatok számára. Tenant schema migration contract réteg.
# Sárközi Mihály - 2026.05.21

"""Migration-state tracking for public and tenant schemas.

Responsibility: ensure the migration-tracking tables exist, list which
revisions have already been applied, and record newly applied revisions.
No DDL creation of application tables; only bookkeeping.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.modules.tenant.schema.ddl import _commit_if_possible
from core.modules.tenant.schema.hooks import TenantSchemaHook, tenant_migration_revision


@dataclass(frozen=True)
class PublicSchemaMigration:
    revision: str
    description: str
    apply: Callable[[Engine], None]


def ensure_public_migration_table(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.platform_schema_migrations (
                revision VARCHAR(255) PRIMARY KEY,
                description VARCHAR(500) NOT NULL DEFAULT '',
                applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """))
        _commit_if_possible(conn)


def ensure_tenant_schema(engine: Engine, slug: str) -> None:
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{slug}"'))
        _commit_if_possible(conn)


def ensure_tenant_migration_table(engine: Engine, slug: str) -> None:
    ensure_tenant_schema(engine, slug)
    with engine.connect() as conn:
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS "{slug}".schema_migrations (
                revision VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """))
        _commit_if_possible(conn)


def list_applied_public_migrations(engine: Engine) -> set[str]:
    ensure_public_migration_table(engine)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT revision FROM public.platform_schema_migrations")).fetchall()
    return {row[0] for row in rows}


def record_public_migration(engine: Engine, migration: PublicSchemaMigration) -> None:
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO public.platform_schema_migrations (revision, description)
                VALUES (:revision, :description)
                ON CONFLICT (revision) DO NOTHING
            """),
            {"revision": migration.revision, "description": migration.description},
        )
        _commit_if_possible(conn)


def list_applied_tenant_migrations(engine: Engine, slug: str) -> set[str]:
    ensure_tenant_migration_table(engine, slug)
    with engine.connect() as conn:
        rows = conn.execute(text(f'SELECT revision FROM "{slug}".schema_migrations')).fetchall()
    return {row[0] for row in rows}


def record_tenant_migration(engine: Engine, slug: str, hook: TenantSchemaHook) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(f"""
                INSERT INTO "{slug}".schema_migrations (revision, name)
                VALUES (:revision, :name)
                ON CONFLICT (revision) DO NOTHING
            """),
            {"revision": tenant_migration_revision(hook), "name": hook.name},
        )
        _commit_if_possible(conn)


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
