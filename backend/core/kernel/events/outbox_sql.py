# backend/core/kernel/events/outbox_sql.py
# Feladat: Az outbox tábla telepítéséhez és kompatibilis sémafrissítéséhez szükséges SQL parancsokat tartalmazza. A runtime/public schema bootstrap és a repository ensure művelete ezt használja, hogy az event outbox infrastruktúra rendelkezésre álljon. Core DB infrastruktúra helper, nem domain migráció.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from sqlalchemy import text


def install_platform_event_outbox(conn) -> None:
    conn.execute(
        text(
            """
        CREATE TABLE IF NOT EXISTS public.platform_event_outbox (
            id SERIAL PRIMARY KEY,
            event_type VARCHAR(64) NOT NULL,
            payload JSONB NOT NULL DEFAULT '{}'::jsonb,
            status VARCHAR(16) NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NULL,
            next_retry_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processed_at TIMESTAMPTZ NULL,
            idempotency_key VARCHAR(128) NULL,
            locked_at TIMESTAMPTZ NULL,
            lock_owner VARCHAR(128) NULL,
            leased_by VARCHAR(128) NULL,
            lease_until TIMESTAMPTZ NULL,
            last_heartbeat_at TIMESTAMPTZ NULL,
            started_at TIMESTAMPTZ NULL,
            finished_at TIMESTAMPTZ NULL
        )
        """
        )
    )
    conn.execute(
        text(
            """
        CREATE INDEX IF NOT EXISTS ix_platform_event_outbox_status_retry
        ON public.platform_event_outbox (status, next_retry_at)
        """
        )
    )
    conn.execute(
        text(
            """
        CREATE INDEX IF NOT EXISTS ix_platform_event_outbox_type_status
        ON public.platform_event_outbox (event_type, status)
        """
        )
    )


def upgrade_platform_event_outbox_schema(conn) -> None:
    stmts = [
        "ALTER TABLE public.platform_event_outbox ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128) NULL",
        "ALTER TABLE public.platform_event_outbox ADD COLUMN IF NOT EXISTS locked_at TIMESTAMPTZ NULL",
        "ALTER TABLE public.platform_event_outbox ADD COLUMN IF NOT EXISTS lock_owner VARCHAR(128) NULL",
        "ALTER TABLE public.platform_event_outbox ADD COLUMN IF NOT EXISTS leased_by VARCHAR(128) NULL",
        "ALTER TABLE public.platform_event_outbox ADD COLUMN IF NOT EXISTS lease_until TIMESTAMPTZ NULL",
        "ALTER TABLE public.platform_event_outbox ADD COLUMN IF NOT EXISTS last_heartbeat_at TIMESTAMPTZ NULL",
        "ALTER TABLE public.platform_event_outbox ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ NULL",
        "ALTER TABLE public.platform_event_outbox ADD COLUMN IF NOT EXISTS finished_at TIMESTAMPTZ NULL",
    ]
    for stmt in stmts:
        conn.execute(text(stmt))
    conn.execute(
        text(
            """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_platform_event_outbox_idempotency_key_unique
        ON public.platform_event_outbox (idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
        )
    )
    conn.execute(
        text(
            """
        CREATE INDEX IF NOT EXISTS ix_platform_event_outbox_lease_until
        ON public.platform_event_outbox (status, lease_until)
        WHERE status = 'processing'
        """
        )
    )
    conn.execute(
        text(
            """
        CREATE INDEX IF NOT EXISTS ix_platform_event_outbox_dead_letter
        ON public.platform_event_outbox (event_type, updated_at)
        WHERE status = 'dead_letter'
        """
        )
    )
    conn.execute(
        text(
            """
        CREATE INDEX IF NOT EXISTS ix_platform_event_outbox_stale_lock
        ON public.platform_event_outbox (status, locked_at)
        WHERE status = 'processing'
        """
        )
    )


__all__ = ["install_platform_event_outbox", "upgrade_platform_event_outbox_schema"]
