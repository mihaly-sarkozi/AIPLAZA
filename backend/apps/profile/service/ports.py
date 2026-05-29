from __future__ import annotations

# backend/apps/profile/service/ports.py
# Feladat: Profile facade és preference service protokolljai a tesztelhető függőségi határokhoz.
# Sárközi Mihály - 2026.05.24

from typing import Protocol, runtime_checkable

from apps.profile.domain.preferences import ProfilePreferences


@runtime_checkable
class CoreProfileServicePort(Protocol):
    def get_me(self, *, user, tenant, training_status_reader=None) -> dict[str, object]:
        ...

    def update_me(
        self,
        *,
        user,
        name: str | None,
        preferred_locale: str | None,
        preferred_theme: str | None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        ...

    def request_email_change(
        self,
        *,
        user,
        new_email: str,
        request_base_url: str | None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        ...

    def invalidate_cache(self, tenant_slug: str | None, user_id: int) -> None:
        ...


@runtime_checkable
class PreferencesRepositoryPort(Protocol):
    def get_for_user(self, *, tenant_slug: str, user_id: int) -> ProfilePreferences:
        ...

    def upsert_for_user(
        self,
        *,
        tenant_slug: str,
        user_id: int,
        dashboard_layout: str,
        show_tips: bool,
    ) -> ProfilePreferences:
        ...


@runtime_checkable
class PreferencesServicePort(Protocol):
    def get_for_user(self, *, tenant_slug: str, user_id: int) -> ProfilePreferences:
        ...

    def update_for_user(
        self,
        *,
        tenant_slug: str,
        user_id: int,
        updates: dict[str, object] | None,
    ) -> ProfilePreferences:
        ...


@runtime_checkable
class ProfileFacadePort(Protocol):
    def get_profile(self, *, user, tenant) -> dict[str, object]:
        ...

    def get_preferences(self, *, user, tenant) -> dict[str, object]:
        ...

    def update_profile(
        self,
        *,
        user,
        tenant,
        name: str | None,
        email: str | None,
        preferred_locale: str | None,
        preferred_theme: str | None,
        app_preferences: dict[str, object] | None,
    ) -> dict[str, object]:
        ...

    def update_preferences(self, *, user, tenant, app_preferences: dict[str, object] | None) -> dict[str, object]:
        ...


__all__ = [
    "CoreProfileServicePort",
    "ProfileFacadePort",
    "PreferencesRepositoryPort",
    "PreferencesServicePort",
]
