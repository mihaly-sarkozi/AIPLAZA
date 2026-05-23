# backend/core/modules/tenant/repositories/demo_signup_repository.py
# Feladat: Demo sign-up session, resend, blocklist és cleanup DML-only persistence adapter. Raw SQL alapú műveletekkel kezeli a demo onboarding átmeneti állapotait és visszaélés-védelmi nyilvántartásait; a táblák létrehozása public schema migrációban történik. Demo signup repository réteg.
# Sárközi Mihály - 2026.05.22

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

DEMO_SESSION_TABLE = "public.demo_signup_sessions"
DEMO_BLOCKLIST_TABLE = "public.demo_signup_blocklist"


class DemoSignupRepository:
    def __init__(self, engine) -> None:
        self._engine = engine

    def ensure_session_table(self) -> None:
        # Runtime repositoryk nem végezhetnek DDL-t. A demo signup public táblák
        # a core.modules.tenant.schema.public migrációs/bootstrap lépésben jönnek létre.
        return None

    def ensure_blocklist_table(self) -> None:
        # Runtime repositoryk nem végezhetnek DDL-t. A demo signup public táblák
        # a core.modules.tenant.schema.public migrációs/bootstrap lépésben jönnek létre.
        return None

    def get_reserved_slug(self, session_id: str) -> str | None:
        self.ensure_session_table()
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT tenant_slug
                    FROM {DEMO_SESSION_TABLE}
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id},
            ).first()
        return str(row[0]) if row else None

    def reserve_slug(self, *, session_id: str, requested_name: str, email: str, tenant_slug: str) -> bool:
        self.ensure_session_table()
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        f"""
                        INSERT INTO {DEMO_SESSION_TABLE} (session_id, requested_name, email, tenant_slug)
                        VALUES (:session_id, :requested_name, :email, :tenant_slug)
                        """
                    ),
                    {
                        "session_id": session_id,
                        "requested_name": requested_name,
                        "email": email,
                        "tenant_slug": tenant_slug,
                    },
                )
            return True
        except IntegrityError:
            return False

    def mark_session_completed(self, session_id: str) -> None:
        self.ensure_session_table()
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    UPDATE {DEMO_SESSION_TABLE}
                    SET completed_at = NOW()
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id},
            )

    def delete_session(self, session_id: str) -> None:
        self.ensure_session_table()
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    DELETE FROM {DEMO_SESSION_TABLE}
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id},
            )

    def find_latest_completed_tenant_slug_by_email(self, email: str) -> str | None:
        normalized_email = (email or "").strip().lower()
        if not normalized_email:
            return None
        self.ensure_session_table()
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT tenant_slug
                    FROM {DEMO_SESSION_TABLE}
                    WHERE LOWER(TRIM(email)) = :email
                      AND completed_at IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"email": normalized_email},
            ).first()
        return str(row[0]) if row else None

    def count_completed_signups_for_email(self, email: str) -> int:
        normalized_email = (email or "").strip().lower()
        if not normalized_email:
            return 0
        self.ensure_session_table()
        with self._engine.begin() as conn:
            value = conn.execute(
                text(
                    f"""
                    SELECT COUNT(1)
                    FROM {DEMO_SESSION_TABLE}
                    WHERE LOWER(TRIM(email)) = :email
                      AND completed_at IS NOT NULL
                    """
                ),
                {"email": normalized_email},
            ).scalar()
        return int(value or 0)

    def has_active_demo_for_email(self, email: str) -> bool:
        normalized_email = (email or "").strip().lower()
        if not normalized_email:
            return False
        self.ensure_session_table()
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT ds.tenant_slug
                    FROM {DEMO_SESSION_TABLE} ds
                    JOIN public.tenants t ON t.slug = ds.tenant_slug
                    LEFT JOIN public.tenant_configs tc ON tc.tenant_id = t.id
                    WHERE LOWER(TRIM(ds.email)) = :email
                      AND ds.completed_at IS NOT NULL
                      AND t.is_active = TRUE
                      AND COALESCE((tc.feature_flags->>'demo_mode')::boolean, FALSE) = TRUE
                      AND (
                        NULLIF(tc.feature_flags->>'demo_expires_at', '') IS NULL
                        OR (tc.feature_flags->>'demo_expires_at')::timestamptz > NOW()
                      )
                    ORDER BY ds.created_at DESC
                    LIMIT 1
                    """
                ),
                {"email": normalized_email},
            ).first()
        return bool(row)

    def cleanup_expired_demo_tenants(self) -> int:
        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    """
                    UPDATE public.tenants t
                    SET is_active = FALSE,
                        updated_at = NOW()
                    FROM public.tenant_configs tc
                    WHERE tc.tenant_id = t.id
                      AND t.is_active = TRUE
                      AND COALESCE((tc.feature_flags->>'demo_mode')::boolean, FALSE) = TRUE
                      AND NULLIF(tc.feature_flags->>'demo_expires_at', '') IS NOT NULL
                      AND (tc.feature_flags->>'demo_expires_at')::timestamptz <= NOW()
                    """
                )
            )
        return int(getattr(result, "rowcount", 0) or 0)

    def is_email_blocked(self, email: str) -> bool:
        normalized_email = (email or "").strip().lower()
        if not normalized_email:
            return False
        self.ensure_blocklist_table()
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT email
                    FROM {DEMO_BLOCKLIST_TABLE}
                    WHERE LOWER(TRIM(email)) = :email
                    LIMIT 1
                    """
                ),
                {"email": normalized_email},
            ).first()
        return bool(row)

    def block_email(self, email: str, *, source_tenant_slug: str, reason: str) -> None:
        normalized_email = (email or "").strip().lower()
        if not normalized_email:
            return
        self.ensure_blocklist_table()
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {DEMO_BLOCKLIST_TABLE} (email, blocked_at, reason, source_tenant_slug)
                    VALUES (:email, NOW(), :reason, :source_tenant_slug)
                    ON CONFLICT (email)
                    DO UPDATE SET
                        blocked_at = EXCLUDED.blocked_at,
                        reason = EXCLUDED.reason,
                        source_tenant_slug = EXCLUDED.source_tenant_slug
                    """
                ),
                {
                    "email": normalized_email,
                    "reason": reason,
                    "source_tenant_slug": source_tenant_slug,
                },
            )
