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


def _apply_public_platform_admin_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.platform_admin_users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) NOT NULL UNIQUE,
                name VARCHAR(255),
                password_hash VARCHAR(255) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                role VARCHAR(20) NOT NULL DEFAULT 'admin',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                created_by INTEGER,
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                updated_by INTEGER,
                deleted_at TIMESTAMPTZ,
                deleted_by INTEGER,
                registration_completed_at TIMESTAMPTZ,
                failed_login_attempts INTEGER NOT NULL DEFAULT 0,
                security_version INTEGER NOT NULL DEFAULT 0
            )
        """))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_admin_users_email ON public.platform_admin_users(LOWER(email))"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_platform_admin_users_created_at ON public.platform_admin_users(created_at)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.platform_admin_invite_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES public.platform_admin_users(id) ON DELETE CASCADE,
                token_hash VARCHAR(255) NOT NULL UNIQUE,
                expires_at TIMESTAMPTZ NOT NULL,
                used_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                created_by INTEGER,
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                updated_by INTEGER
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_platform_admin_invite_tokens_user_id ON public.platform_admin_invite_tokens(user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_platform_admin_invite_tokens_hash ON public.platform_admin_invite_tokens(token_hash)"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.platform_admin_refresh_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES public.platform_admin_users(id) ON DELETE CASCADE,
                jti VARCHAR(128) NOT NULL UNIQUE,
                token_hash VARCHAR(255) NOT NULL,
                ip VARCHAR(64),
                user_agent VARCHAR(255),
                valid BOOLEAN NOT NULL DEFAULT TRUE,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                created_by INTEGER,
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                updated_by INTEGER
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_platform_admin_refresh_tokens_user_valid ON public.platform_admin_refresh_tokens(user_id, valid)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_platform_admin_refresh_tokens_jti ON public.platform_admin_refresh_tokens(jti)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_platform_admin_refresh_tokens_hash ON public.platform_admin_refresh_tokens(token_hash)"))
        _commit_if_possible(conn)


def _apply_public_platform_admin_refresh_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS public.platform_admin_refresh_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES public.platform_admin_users(id) ON DELETE CASCADE,
                jti VARCHAR(128) NOT NULL UNIQUE,
                token_hash VARCHAR(255) NOT NULL,
                ip VARCHAR(64),
                user_agent VARCHAR(255),
                valid BOOLEAN NOT NULL DEFAULT TRUE,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                created_by INTEGER,
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                updated_by INTEGER
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_platform_admin_refresh_tokens_user_valid ON public.platform_admin_refresh_tokens(user_id, valid)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_platform_admin_refresh_tokens_jti ON public.platform_admin_refresh_tokens(jti)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_platform_admin_refresh_tokens_hash ON public.platform_admin_refresh_tokens(token_hash)"))
        _commit_if_possible(conn)


def _apply_public_channel_access_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.channel_credentials (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
                    channel_type VARCHAR(16) NOT NULL DEFAULT 'widget',
                    name VARCHAR(120) NOT NULL,
                    key_prefix VARCHAR(32) NOT NULL,
                    secret_hash VARCHAR(255) NOT NULL,
                    status VARCHAR(16) NOT NULL DEFAULT 'active',
                    allowed_kb_uuids JSONB NOT NULL DEFAULT '[]'::jsonb,
                    daily_limit INTEGER NOT NULL DEFAULT 200,
                    per_minute_limit INTEGER NOT NULL DEFAULT 30,
                    allowed_origins JSONB NOT NULL DEFAULT '[]'::jsonb,
                    expires_at TIMESTAMPTZ,
                    last_used_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_by INTEGER,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_by INTEGER,
                    revoked_at TIMESTAMPTZ,
                    revoked_by INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_channel_credentials_tenant_name
                ON public.channel_credentials(tenant_id, name)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_channel_credentials_tenant_status
                ON public.channel_credentials(tenant_id, status)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.channel_usage_events (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
                    credential_id INTEGER NOT NULL REFERENCES public.channel_credentials(id) ON DELETE CASCADE,
                    channel_type VARCHAR(16) NOT NULL DEFAULT 'widget',
                    period_key VARCHAR(16) NOT NULL,
                    status VARCHAR(16) NOT NULL DEFAULT 'ok',
                    question TEXT NOT NULL DEFAULT '',
                    kb_uuid VARCHAR(64),
                    query_run_id VARCHAR(64),
                    response_ms INTEGER NOT NULL DEFAULT 0,
                    llm_ms INTEGER NOT NULL DEFAULT 0,
                    context_build_ms INTEGER NOT NULL DEFAULT 0,
                    total_ms INTEGER NOT NULL DEFAULT 0,
                    remote_ip VARCHAR(64),
                    origin VARCHAR(255),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_channel_usage_events_tenant_period ON public.channel_usage_events(tenant_id, period_key)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_channel_usage_events_credential_created ON public.channel_usage_events(credential_id, created_at DESC)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_channel_usage_events_query_run ON public.channel_usage_events(query_run_id)"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.channel_feedback_events (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
                    credential_id INTEGER REFERENCES public.channel_credentials(id) ON DELETE SET NULL,
                    channel_type VARCHAR(16) NOT NULL DEFAULT 'widget',
                    query_run_id VARCHAR(64),
                    trace_id VARCHAR(96),
                    helpful BOOLEAN,
                    reason VARCHAR(120),
                    note TEXT,
                    triage_status VARCHAR(24) NOT NULL DEFAULT 'new',
                    triage_owner VARCHAR(120),
                    triage_note TEXT,
                    triaged_at TIMESTAMPTZ,
                    triaged_by INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_channel_feedback_events_tenant_created ON public.channel_feedback_events(tenant_id, created_at DESC)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_channel_feedback_events_query_run ON public.channel_feedback_events(query_run_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_channel_feedback_events_triage_status ON public.channel_feedback_events(triage_status)"))
        _commit_if_possible(conn)


def _apply_public_platform_admin_mfa_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE public.platform_admin_users ADD COLUMN IF NOT EXISTS mfa_enabled BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE public.platform_admin_users ADD COLUMN IF NOT EXISTS mfa_secret_base32 VARCHAR(128)"))
        conn.execute(text("ALTER TABLE public.platform_admin_users ADD COLUMN IF NOT EXISTS mfa_pending_secret_base32 VARCHAR(128)"))
        conn.execute(text("ALTER TABLE public.platform_admin_users ADD COLUMN IF NOT EXISTS mfa_pending_expires_at TIMESTAMPTZ"))
        conn.execute(text("ALTER TABLE public.platform_admin_users ADD COLUMN IF NOT EXISTS mfa_recovery_codes_hashes TEXT NOT NULL DEFAULT '[]'"))
        _commit_if_possible(conn)


def _apply_public_platform_admin_mfa_attempts_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.platform_admin_mfa_attempts (
                    id SERIAL PRIMARY KEY,
                    scope VARCHAR(32) NOT NULL,
                    scope_key VARCHAR(128) NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    window_started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    blocked_until TIMESTAMPTZ,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    created_by INTEGER,
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_by INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_platform_admin_mfa_attempt_scope_key
                ON public.platform_admin_mfa_attempts(scope, scope_key)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_platform_admin_mfa_attempt_blocked
                ON public.platform_admin_mfa_attempts(blocked_until)
                """
            )
        )
        _commit_if_possible(conn)


def _public_migrations() -> tuple[PublicSchemaMigration, ...]:
    from core.platform.events.outbox import ensure_platform_event_outbox
    from core.platform_admin.schema_migrations import apply_platform_security_alerts_legacy_compat

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
        PublicSchemaMigration(
            revision="platform.public.0003_platform_admin",
            description="Platform admin users and password setup tokens",
            apply=_apply_public_platform_admin_schema,
        ),
        PublicSchemaMigration(
            revision="platform.public.0004_platform_admin_refresh_tokens",
            description="Platform admin refresh token sessions",
            apply=_apply_public_platform_admin_refresh_schema,
        ),
        PublicSchemaMigration(
            revision="platform.public.0005_platform_security_alerts_legacy_compat",
            description="Normalize legacy platform security alerts schema",
            apply=apply_platform_security_alerts_legacy_compat,
        ),
        PublicSchemaMigration(
            revision="platform.public.0006_channel_access",
            description="Channel credentials, usage and feedback analytics tables",
            apply=_apply_public_channel_access_schema,
        ),
        PublicSchemaMigration(
            revision="platform.public.0007_platform_admin_mfa",
            description="Platform admin MFA fields (TOTP + recovery codes)",
            apply=_apply_public_platform_admin_mfa_schema,
        ),
        PublicSchemaMigration(
            revision="platform.public.0008_platform_admin_mfa_attempts",
            description="Platform admin MFA attempt counters and lockouts",
            apply=_apply_public_platform_admin_mfa_attempts_schema,
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
