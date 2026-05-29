from __future__ import annotations

# backend/apps/profile/infra/preferences_repository.py
# Feladat: Tenant sémás profile_preferences repository a profil felületi preferenciáinak perzisztálásához.
# Sárközi Mihály - 2026.05.24

import re

from sqlalchemy import text

from apps.profile.domain.preferences import ProfilePreferences

_SAFE_SCHEMA_RE = re.compile(r"^[a-z0-9_]+$")
_TABLE_NAME = "profile_preferences"


def _safe_schema_name(tenant_slug: str) -> str:
    schema = (tenant_slug or "").strip().lower()
    if not schema or not _SAFE_SCHEMA_RE.match(schema):
        raise ValueError(f"invalid tenant schema: {tenant_slug!r}")
    return schema


class ProfilePreferencesRepository:
    def __init__(self, engine) -> None:
        self._engine = engine

    def get_for_user(self, *, tenant_slug: str, user_id: int) -> ProfilePreferences:
        schema = _safe_schema_name(tenant_slug)
        table_name = f'"{schema}"."{_TABLE_NAME}"'
        with self._engine.begin() as conn:
            row = conn.execute(
                text(
                    f"""
                    SELECT user_id, dashboard_layout, show_tips
                    FROM {table_name}
                    WHERE user_id = :user_id
                    LIMIT 1
                    """
                ),
                {"user_id": user_id},
            ).first()
        if row is None:
            return ProfilePreferences(user_id=user_id)
        return ProfilePreferences(
            user_id=int(row[0]),
            dashboard_layout=str(row[1] or "comfortable"),
            show_tips=bool(row[2]),
        )

    def upsert_for_user(
        self,
        *,
        tenant_slug: str,
        user_id: int,
        dashboard_layout: str,
        show_tips: bool,
    ) -> ProfilePreferences:
        schema = _safe_schema_name(tenant_slug)
        table_name = f'"{schema}"."{_TABLE_NAME}"'
        with self._engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    INSERT INTO {table_name} (user_id, dashboard_layout, show_tips)
                    VALUES (:user_id, :dashboard_layout, :show_tips)
                    ON CONFLICT (user_id) DO UPDATE
                    SET dashboard_layout = EXCLUDED.dashboard_layout,
                        show_tips = EXCLUDED.show_tips,
                        updated_at = NOW()
                    """
                ),
                {
                    "user_id": user_id,
                    "dashboard_layout": dashboard_layout,
                    "show_tips": show_tips,
                },
            )
        return ProfilePreferences(
            user_id=user_id,
            dashboard_layout=dashboard_layout,
            show_tips=show_tips,
        )


__all__ = ["ProfilePreferencesRepository"]
