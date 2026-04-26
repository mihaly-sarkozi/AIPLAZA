from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

DEMO_SESSION_TABLE = "public.demo_signup_sessions"
DEMO_BLOCKLIST_TABLE = "public.demo_signup_blocklist"


class DemoSignupRepository:
    def __init__(self, engine) -> None:
        self._engine = engine

    def ensure_session_table(self) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {DEMO_SESSION_TABLE} (
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

    def ensure_blocklist_table(self) -> None:
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    text(
                        f"""
                        CREATE TABLE IF NOT EXISTS {DEMO_BLOCKLIST_TABLE} (
                            email VARCHAR(255) PRIMARY KEY,
                            blocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            reason TEXT NULL,
                            source_tenant_slug VARCHAR(64) NULL
                        )
                        """
                    )
                )
        except IntegrityError:
            return

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
