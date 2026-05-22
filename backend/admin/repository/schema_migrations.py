# backend/admin/repository/schema_migrations.py
# Feladat: A platform_security_alerts tábla legacy sémaváltozatainak kompatibilis normalizálását végzi. Létrehozza vagy kiegészíti a public táblát, feltölti a kötelező mezők hiányzó értékeit és indexeket biztosít. Admin perzisztencia migrációs helper, amelyet startup/provisioning és script is hívhat.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.modules.tenant.schema.ddl import _commit_if_possible


def apply_platform_security_alerts_legacy_compat(engine: Engine) -> None:
    """Normalize legacy platform_security_alerts schema variants."""
    with engine.connect() as conn:
        def _column_exists(column_name: str) -> bool:
            return bool(
                conn.execute(
                    text(
                        """
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_schema = 'public'
                          AND table_name = 'platform_security_alerts'
                          AND column_name = :column_name
                        LIMIT 1
                        """
                    ),
                    {"column_name": column_name},
                ).scalar()
            )

        conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS public.platform_security_alerts (
                    id SERIAL PRIMARY KEY,
                    alert_key VARCHAR(255) NOT NULL UNIQUE,
                    category VARCHAR(64) NOT NULL,
                    severity VARCHAR(16) NOT NULL,
                    signal VARCHAR(255) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    value INTEGER NOT NULL DEFAULT 0,
                    hit_count INTEGER NOT NULL DEFAULT 1,
                    status VARCHAR(16) NOT NULL DEFAULT 'open',
                    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
                    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
                    acknowledged_at TIMESTAMPTZ,
                    acknowledged_by INTEGER,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    created_by INTEGER,
                    updated_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_by INTEGER
                )
                """
            )
        )
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS alert_key VARCHAR(255)"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS category VARCHAR(64)"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS severity VARCHAR(16)"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS signal VARCHAR(255)"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS title VARCHAR(255)"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS value INTEGER"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS hit_count INTEGER"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS status VARCHAR(16)"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMPTZ"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS acknowledged_by INTEGER"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS created_by INTEGER"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS updated_by INTEGER"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ DEFAULT NOW()"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ DEFAULT NOW()"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ALTER COLUMN alert_key DROP NOT NULL"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ALTER COLUMN category DROP NOT NULL"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ALTER COLUMN severity DROP NOT NULL"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ALTER COLUMN signal DROP NOT NULL"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ALTER COLUMN title DROP NOT NULL"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ALTER COLUMN value DROP NOT NULL"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ALTER COLUMN hit_count DROP NOT NULL"))
        conn.execute(text("ALTER TABLE public.platform_security_alerts ALTER COLUMN status DROP NOT NULL"))
        rule_key_exists = _column_exists("rule_key")
        event_count_exists = _column_exists("event_count")
        last_value_exists = _column_exists("last_value")
        alert_key_expr = "COALESCE(NULLIF(alert_key, ''), CONCAT('legacy:', id::text))"
        if rule_key_exists:
            alert_key_expr = "COALESCE(NULLIF(alert_key, ''), NULLIF(rule_key, ''), CONCAT('legacy:', id::text))"
        value_expr = "COALESCE(value, 0)"
        if last_value_exists:
            value_expr = "COALESCE(value, last_value, 0)"
        hit_count_expr = "COALESCE(hit_count, 1)"
        if event_count_exists:
            hit_count_expr = "COALESCE(hit_count, event_count, 1)"
        conn.execute(
            text(
                f"""
                UPDATE public.platform_security_alerts
                SET
                  alert_key = {alert_key_expr},
                  category = COALESCE(NULLIF(category, ''), 'security'),
                  severity = COALESCE(NULLIF(severity, ''), 'medium'),
                  signal = COALESCE(NULLIF(signal, ''), NULLIF(title, ''), 'legacy_alert'),
                  title = COALESCE(NULLIF(title, ''), NULLIF(signal, ''), 'legacy_alert'),
                  value = {value_expr},
                  hit_count = {hit_count_expr},
                  status = COALESCE(NULLIF(status, ''), 'open')
                WHERE
                  alert_key IS NULL OR alert_key = ''
                  OR category IS NULL OR category = ''
                  OR severity IS NULL OR severity = ''
                  OR signal IS NULL OR signal = ''
                  OR title IS NULL OR title = ''
                  OR value IS NULL
                  OR hit_count IS NULL
                  OR status IS NULL OR status = ''
                """
            )
        )
        if rule_key_exists:
            conn.execute(text("ALTER TABLE public.platform_security_alerts ALTER COLUMN rule_key DROP NOT NULL"))
            conn.execute(
                text(
                    """
                    UPDATE public.platform_security_alerts
                    SET rule_key = COALESCE(NULLIF(rule_key, ''), alert_key)
                    WHERE rule_key IS NULL OR rule_key = ''
                    """
                )
            )
        if event_count_exists:
            conn.execute(text("ALTER TABLE public.platform_security_alerts ALTER COLUMN event_count DROP NOT NULL"))
        if last_value_exists:
            conn.execute(text("ALTER TABLE public.platform_security_alerts ALTER COLUMN last_value DROP NOT NULL"))
        if event_count_exists or last_value_exists:
            conn.execute(
                text(
                    """
                    UPDATE public.platform_security_alerts
                    SET
                      event_count = COALESCE(event_count, hit_count, 1),
                      last_value = COALESCE(last_value, value, 0)
                    WHERE event_count IS NULL OR last_value IS NULL
                    """
                )
            )
        conn.execute(
            text(
                """
                ALTER TABLE public.platform_security_alerts
                ALTER COLUMN alert_key SET NOT NULL,
                ALTER COLUMN category SET NOT NULL,
                ALTER COLUMN severity SET NOT NULL,
                ALTER COLUMN signal SET NOT NULL,
                ALTER COLUMN title SET NOT NULL,
                ALTER COLUMN value SET NOT NULL,
                ALTER COLUMN hit_count SET NOT NULL,
                ALTER COLUMN status SET NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ix_platform_security_alerts_alert_key
                ON public.platform_security_alerts(alert_key)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_platform_security_alerts_category
                ON public.platform_security_alerts(category)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_platform_security_alerts_severity
                ON public.platform_security_alerts(severity)
                """
            )
        )
        _commit_if_possible(conn)

