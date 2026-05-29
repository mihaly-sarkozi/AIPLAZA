from __future__ import annotations

# backend/apps/profile/service/preferences_service.py
# Feladat: Profile felületi preferenciák domain service-e layout validációval és repository delegálással.
# Sárközi Mihály - 2026.05.24

from apps.profile.domain.preferences import ProfilePreferences
from apps.profile.service.ports import PreferencesRepositoryPort

_ALLOWED_DASHBOARD_LAYOUTS = {"comfortable", "compact"}


class ProfilePreferencesService:
    def __init__(self, repository: PreferencesRepositoryPort) -> None:
        self._repository = repository

    def get_for_user(self, *, tenant_slug: str, user_id: int) -> ProfilePreferences:
        return self._repository.get_for_user(tenant_slug=tenant_slug, user_id=user_id)

    def update_for_user(
        self,
        *,
        tenant_slug: str,
        user_id: int,
        updates: dict[str, object] | None,
    ) -> ProfilePreferences:
        current = self.get_for_user(tenant_slug=tenant_slug, user_id=user_id)
        payload = dict(updates or {})
        dashboard_layout = str(payload.get("dashboard_layout") or current.dashboard_layout).strip().lower()
        if dashboard_layout not in _ALLOWED_DASHBOARD_LAYOUTS:
            dashboard_layout = current.dashboard_layout
        show_tips_value = payload.get("show_tips", current.show_tips)
        show_tips = bool(show_tips_value) if show_tips_value is not None else current.show_tips
        return self._repository.upsert_for_user(
            tenant_slug=tenant_slug,
            user_id=user_id,
            dashboard_layout=dashboard_layout,
            show_tips=show_tips,
        )


__all__ = ["ProfilePreferencesService"]
