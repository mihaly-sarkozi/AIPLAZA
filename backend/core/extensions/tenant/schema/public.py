"""Public schema creation and upgrade.

Responsibility: define the public-schema DDL (tenants, tenant_configs,
tenant_domains, event outbox) and orchestrate idempotent upgrades via the
migration-tracking table.  No tenant-schema logic here.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.extensions.tenant.schema.ddl import _commit_if_possible
from core.extensions.tenant.schema.migrations import (
    PublicSchemaMigration,
    list_applied_public_migrations,
    record_public_migration,
)


def _apply_public_core_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.tenants (
                id SERIAL PRIMARY KEY,
                slug VARCHAR(64) NOT NULL UNIQUE,
                name VARCHAR(255) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                created_by INTEGER,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_by INTEGER,
                security_version INTEGER NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT TRUE
            )
        """))
        conn.execute(text("ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS created_by INTEGER"))
        conn.execute(text("ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"))
        conn.execute(text("ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS updated_by INTEGER"))
        conn.execute(text("ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS security_version INTEGER NOT NULL DEFAULT 0"))
        conn.execute(text("ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.tenant_configs (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE UNIQUE,
                package VARCHAR(64) NOT NULL DEFAULT 'free',
                feature_flags JSONB NOT NULL DEFAULT '{}',
                limits JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_by INTEGER,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_by INTEGER
            )
        """))
        conn.execute(text("ALTER TABLE public.tenant_configs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"))
        conn.execute(text("ALTER TABLE public.tenant_configs ADD COLUMN IF NOT EXISTS created_by INTEGER"))
        conn.execute(text("ALTER TABLE public.tenant_configs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"))
        conn.execute(text("ALTER TABLE public.tenant_configs ADD COLUMN IF NOT EXISTS updated_by INTEGER"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_configs_tenant_id ON public.tenant_configs(tenant_id)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.tenant_domains (
                id SERIAL PRIMARY KEY,
                tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
                domain VARCHAR(255) NOT NULL,
                verified_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_by INTEGER,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_by INTEGER
            )
        """))
        conn.execute(text("ALTER TABLE public.tenant_domains ADD COLUMN IF NOT EXISTS created_by INTEGER"))
        conn.execute(text("ALTER TABLE public.tenant_domains ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()"))
        conn.execute(text("ALTER TABLE public.tenant_domains ADD COLUMN IF NOT EXISTS updated_by INTEGER"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_tenant_domains_domain ON public.tenant_domains(domain)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_domains_tenant_id ON public.tenant_domains(tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_domains_domain ON public.tenant_domains(domain)"))
        _commit_if_possible(conn)


def _public_migrations() -> tuple[PublicSchemaMigration, ...]:
    from core.platform.events.outbox import ensure_platform_event_outbox

    return (
        PublicSchemaMigration(
            revision="platform.public.0001_core",
            description="Core public tenant tables and indexes",
            apply=_apply_public_core_schema,
        ),
        PublicSchemaMigration(
            revision="platform.public.0002_event_outbox",
            description="Platform event outbox table",
            apply=ensure_platform_event_outbox,
        ),
    )


def upgrade_public_schema(engine: Engine) -> None:
    """Apply all pending public-schema migrations idempotently."""
    applied = list_applied_public_migrations(engine)
    for migration in _public_migrations():
        if migration.revision in applied:
            continue
        migration.apply(engine)
        record_public_migration(engine, migration)
        applied.add(migration.revision)


__all__ = ["upgrade_public_schema"]
