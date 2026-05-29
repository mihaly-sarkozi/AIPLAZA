# backend/core/modules/tenant/schema/public.py
# Feladat: Public schema migrációs és bootstrap logikát tartalmaz. Tenant, domain, config és több platform-szintű public tábla/index idempotens létrehozását végzi, ezért nagy blast radiusú platform bootstrap fájl. Public schema migration adapter.
# Sárközi Mihály - 2026.05.21

"""Public schema creation and upgrade.

Responsibility: define the public-schema DDL (tenants, tenant_configs,
tenant_domains, event outbox) and orchestrate idempotent upgrades via the
migration-tracking table.  No tenant-schema logic here.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.modules.tenant.schema.ddl import _commit_if_possible
from core.modules.tenant.schema.migrations import (
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
                    active_secret_hash VARCHAR(255),
                    secret_hash VARCHAR(255) NOT NULL,
                    next_key_prefix VARCHAR(32),
                    next_secret_hash VARCHAR(255),
                    secret_version VARCHAR(16) NOT NULL DEFAULT 'active',
                    rotating_until TIMESTAMPTZ,
                    status VARCHAR(16) NOT NULL DEFAULT 'active',
                    allowed_kb_uuids JSONB NOT NULL DEFAULT '[]'::jsonb,
                    daily_limit INTEGER NOT NULL DEFAULT 200,
                    per_minute_limit INTEGER NOT NULL DEFAULT 30,
                    allowed_origins JSONB NOT NULL DEFAULT '[]'::jsonb,
                    allowed_ip_ranges JSONB NOT NULL DEFAULT '[]'::jsonb,
                    require_signed_requests BOOLEAN NOT NULL DEFAULT FALSE,
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
        conn.execute(text("ALTER TABLE public.channel_credentials ADD COLUMN IF NOT EXISTS allowed_ip_ranges JSONB NOT NULL DEFAULT '[]'::jsonb"))
        conn.execute(text("ALTER TABLE public.channel_credentials ADD COLUMN IF NOT EXISTS require_signed_requests BOOLEAN NOT NULL DEFAULT FALSE"))
        conn.execute(text("ALTER TABLE public.channel_credentials ADD COLUMN IF NOT EXISTS active_secret_hash VARCHAR(255)"))
        conn.execute(text("ALTER TABLE public.channel_credentials ADD COLUMN IF NOT EXISTS next_key_prefix VARCHAR(32)"))
        conn.execute(text("ALTER TABLE public.channel_credentials ADD COLUMN IF NOT EXISTS next_secret_hash VARCHAR(255)"))
        conn.execute(text("ALTER TABLE public.channel_credentials ADD COLUMN IF NOT EXISTS secret_version VARCHAR(16) NOT NULL DEFAULT 'active'"))
        conn.execute(text("ALTER TABLE public.channel_credentials ADD COLUMN IF NOT EXISTS rotating_until TIMESTAMPTZ"))
        conn.execute(
            text(
                """
                UPDATE public.channel_credentials
                SET active_secret_hash = secret_hash
                WHERE active_secret_hash IS NULL
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
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_channel_credentials_key_prefix ON public.channel_credentials(key_prefix)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_channel_credentials_next_key_prefix ON public.channel_credentials(next_key_prefix)"))
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
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_channel_feedback_events_trace_id ON public.channel_feedback_events(trace_id)"))
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


def _apply_public_billing_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.billing_catalog_entries (
                    id SERIAL PRIMARY KEY,
                    entry_type VARCHAR(32) NOT NULL,
                    code VARCHAR(64) NOT NULL,
                    name VARCHAR(120) NOT NULL,
                    currency VARCHAR(8) NOT NULL DEFAULT 'EUR',
                    price_cents INTEGER NOT NULL DEFAULT 0,
                    included JSONB NOT NULL DEFAULT '{}'::jsonb,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_billing_catalog_entry_type_code UNIQUE (entry_type, code)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.billing_subscriptions (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
                    plan_code VARCHAR(64) NOT NULL DEFAULT 'free',
                    billing_period VARCHAR(16) NOT NULL DEFAULT 'monthly',
                    status VARCHAR(24) NOT NULL DEFAULT 'trial',
                    trial_started_at TIMESTAMPTZ,
                    trial_ends_at TIMESTAMPTZ,
                    extra_kb_count INTEGER NOT NULL DEFAULT 0,
                    extra_storage_gb INTEGER NOT NULL DEFAULT 0,
                    carryover_addon_questions INTEGER NOT NULL DEFAULT 0,
                    carryover_training_chars BIGINT NOT NULL DEFAULT 0,
                    scheduled_plan_code VARCHAR(64),
                    scheduled_billing_period VARCHAR(16),
                    scheduled_change_effective_period VARCHAR(16),
                    question_warning_period_key VARCHAR(16),
                    question_warning_level INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_billing_subscriptions_tenant UNIQUE (tenant_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.billing_question_usage (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL,
                    period_key VARCHAR(16) NOT NULL,
                    question_count INTEGER NOT NULL DEFAULT 0,
                    last_question_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_billing_question_usage_tenant_user_period
                        UNIQUE (tenant_id, user_id, period_key)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.billing_training_usage (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
                    period_key VARCHAR(16) NOT NULL,
                    trained_chars BIGINT NOT NULL DEFAULT 0,
                    storage_bytes BIGINT NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_billing_training_usage_tenant_period UNIQUE (tenant_id, period_key)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.billing_invoices (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
                    invoice_type VARCHAR(32) NOT NULL,
                    period_key VARCHAR(16) NOT NULL,
                    status VARCHAR(24) NOT NULL DEFAULT 'issued',
                    currency VARCHAR(8) NOT NULL DEFAULT 'EUR',
                    total_cents INTEGER NOT NULL DEFAULT 0,
                    payment_method VARCHAR(32) NOT NULL DEFAULT 'simulated_card',
                    description VARCHAR(255) NOT NULL DEFAULT '',
                    lines JSONB NOT NULL DEFAULT '[]'::jsonb,
                    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    due_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_billing_invoice_tenant_type_period
                        UNIQUE (tenant_id, invoice_type, period_key)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.billing_payment_events (
                    id SERIAL PRIMARY KEY,
                    provider VARCHAR(32) NOT NULL,
                    event_id VARCHAR(128) NOT NULL,
                    event_type VARCHAR(96) NOT NULL,
                    tenant_id INTEGER REFERENCES public.tenants(id) ON DELETE CASCADE,
                    status VARCHAR(24) NOT NULL DEFAULT 'processed',
                    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_billing_payment_event_provider_event UNIQUE (provider, event_id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.billing_debug_state (
                    id SERIAL PRIMARY KEY,
                    simulated_date DATE,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.tenant_cancellation_requests (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
                    tenant_slug VARCHAR(64) NOT NULL,
                    requested_by_user_id INTEGER,
                    reason_code VARCHAR(64) NOT NULL,
                    reason_text VARCHAR(2000) NOT NULL DEFAULT '',
                    active_kb_count INTEGER NOT NULL DEFAULT 0,
                    status VARCHAR(32) NOT NULL DEFAULT 'deactivation_requested',
                    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    effective_at TIMESTAMPTZ,
                    notice_two_days_sent_at TIMESTAMPTZ,
                    notice_one_day_sent_at TIMESTAMPTZ,
                    notice_expired_sent_at TIMESTAMPTZ,
                    deactivated_at TIMESTAMPTZ,
                    cleanup_completed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_billing_question_usage_tenant_id ON public.billing_question_usage (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_billing_question_usage_user_id ON public.billing_question_usage (user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_billing_question_usage_period_key ON public.billing_question_usage (period_key)"))
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_billing_question_usage_tenant_period
                ON public.billing_question_usage (tenant_id, period_key)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_billing_invoices_tenant_issued
                ON public.billing_invoices (tenant_id, issued_at DESC)
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_billing_training_usage_tenant_id ON public.billing_training_usage (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_billing_training_usage_period_key ON public.billing_training_usage (period_key)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_billing_invoices_tenant_id ON public.billing_invoices (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_billing_invoices_period_key ON public.billing_invoices (period_key)"))
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_billing_payment_events_tenant_created
                ON public.billing_payment_events (tenant_id, created_at DESC)
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_billing_payment_events_provider ON public.billing_payment_events (provider)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_billing_payment_events_tenant_id ON public.billing_payment_events (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_billing_payment_events_status ON public.billing_payment_events (status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_billing_payment_events_created_at ON public.billing_payment_events (created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_cancellation_requests_tenant_id ON public.tenant_cancellation_requests (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_cancellation_requests_tenant_slug ON public.tenant_cancellation_requests (tenant_slug)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_cancellation_requests_requested_by_user_id ON public.tenant_cancellation_requests (requested_by_user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_cancellation_requests_status ON public.tenant_cancellation_requests (status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_cancellation_requests_requested_at ON public.tenant_cancellation_requests (requested_at)"))
        _commit_if_possible(conn)


def _apply_public_platform_security_ip_bans_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.platform_security_ip_bans (
                    id SERIAL PRIMARY KEY,
                    ip VARCHAR(64) NOT NULL UNIQUE,
                    reason VARCHAR(255),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    created_by INTEGER,
                    expires_at TIMESTAMPTZ,
                    released_at TIMESTAMPTZ,
                    released_by INTEGER
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ix_platform_security_ip_bans_ip
                ON public.platform_security_ip_bans(ip)
                """
            )
        )
        _commit_if_possible(conn)


def _apply_public_demo_signup_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.demo_signup_sessions (
                    session_id VARCHAR(128) PRIMARY KEY,
                    requested_name VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    tenant_slug VARCHAR(64) NOT NULL UNIQUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_demo_signup_sessions_email_completed
                ON public.demo_signup_sessions(LOWER(TRIM(email)), completed_at)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.demo_signup_blocklist (
                    email VARCHAR(255) PRIMARY KEY,
                    blocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    reason TEXT NULL,
                    source_tenant_slug VARCHAR(64) NULL
                )
                """
            )
        )
        _commit_if_possible(conn)


def _apply_public_tenant_cancellation_requests_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.tenant_cancellation_requests (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
                    tenant_slug VARCHAR(64) NOT NULL,
                    requested_by_user_id INTEGER,
                    reason_code VARCHAR(64) NOT NULL,
                    reason_text VARCHAR(2000) NOT NULL DEFAULT '',
                    active_kb_count INTEGER NOT NULL DEFAULT 0,
                    status VARCHAR(32) NOT NULL DEFAULT 'deactivation_requested',
                    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    effective_at TIMESTAMPTZ,
                    notice_two_days_sent_at TIMESTAMPTZ,
                    notice_one_day_sent_at TIMESTAMPTZ,
                    notice_expired_sent_at TIMESTAMPTZ,
                    deactivated_at TIMESTAMPTZ,
                    cleanup_completed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_cancellation_requests_tenant_id ON public.tenant_cancellation_requests (tenant_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_cancellation_requests_tenant_slug ON public.tenant_cancellation_requests (tenant_slug)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_cancellation_requests_requested_by_user_id ON public.tenant_cancellation_requests (requested_by_user_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_cancellation_requests_status ON public.tenant_cancellation_requests (status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tenant_cancellation_requests_requested_at ON public.tenant_cancellation_requests (requested_at)"))
        _commit_if_possible(conn)


def _apply_public_tenant_cancellation_notifications_schema(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE public.tenant_cancellation_requests
                ADD COLUMN IF NOT EXISTS notice_two_days_sent_at TIMESTAMPTZ
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE public.tenant_cancellation_requests
                ADD COLUMN IF NOT EXISTS notice_one_day_sent_at TIMESTAMPTZ
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE public.tenant_cancellation_requests
                ADD COLUMN IF NOT EXISTS notice_expired_sent_at TIMESTAMPTZ
                """
            )
        )
        _commit_if_possible(conn)


def _public_migrations() -> tuple[PublicSchemaMigration, ...]:
    from core.kernel.events.outbox import ensure_platform_event_outbox
    from admin.repository.schema_migrations import apply_platform_security_alerts_legacy_compat

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
        PublicSchemaMigration(
            revision="platform.public.0009_billing",
            description="Billing public tables and indexes",
            apply=_apply_public_billing_schema,
        ),
        PublicSchemaMigration(
            revision="platform.public.0010_platform_security_ip_bans",
            description="Platform security IP ban table and indexes",
            apply=_apply_public_platform_security_ip_bans_schema,
        ),
        PublicSchemaMigration(
            revision="platform.public.0011_demo_signup_state",
            description="Demo signup session and blocklist tables",
            apply=_apply_public_demo_signup_schema,
        ),
        PublicSchemaMigration(
            revision="platform.public.0012_tenant_cancellation_requests",
            description="Tenant cancellation request records for subscription cancellation flow",
            apply=_apply_public_tenant_cancellation_requests_schema,
        ),
        PublicSchemaMigration(
            revision="platform.public.0013_tenant_cancellation_notifications",
            description="Tenant cancellation notification tracking columns",
            apply=_apply_public_tenant_cancellation_notifications_schema,
        ),
    )


def public_schema_migration_revisions() -> tuple[str, ...]:
    return tuple(migration.revision for migration in _public_migrations())


def upgrade_public_schema(engine: Engine) -> None:
    """Apply all pending public-schema migrations idempotently."""
    applied = list_applied_public_migrations(engine)
    for migration in _public_migrations():
        if migration.revision in applied:
            continue
        migration.apply(engine)
        record_public_migration(engine, migration)
        applied.add(migration.revision)


__all__ = ["public_schema_migration_revisions", "upgrade_public_schema"]
