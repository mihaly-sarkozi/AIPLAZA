from __future__ import annotations

# backend/apps/profile/service/profile_facade.py
# Feladat: App-szintű profile orchestrator a core profile service és profile preference service között.
# Sárközi Mihály - 2026.05.24

from apps.profile.mappers.profile_mapper import build_profile_preferences_response, build_profile_response
from apps.profile.service.ports import (
    CoreProfileServicePort,
    PreferencesServicePort,
)


class ProfileFacade:
    def __init__(
        self,
        *,
        core_profile_service: CoreProfileServicePort,
        preferences_service: PreferencesServicePort,
        training_status_reader=None,
    ) -> None:
        self._core_profile_service = core_profile_service
        self._preferences = preferences_service
        self._training_status_reader = training_status_reader

    def get_profile(self, *, user, tenant) -> dict[str, object]:
        core_payload = self._core_profile_service.get_me(
            user=user,
            tenant=tenant,
            training_status_reader=self._training_status_reader,
        )
        prefs = self._preferences.get_for_user(
            tenant_slug=tenant.slug or "",
            user_id=user.id,
        )
        return build_profile_response(core_payload, prefs)

    def get_preferences(self, *, user, tenant) -> dict[str, object]:
        prefs = self._preferences.get_for_user(
            tenant_slug=tenant.slug or "",
            user_id=user.id,
        )
        return build_profile_preferences_response(prefs)

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
        request_base_url: str | None = None,
    ) -> dict[str, object]:
        core_fields_changed = any(v is not None for v in (name, preferred_locale, preferred_theme))
        effective_user = user
        if core_fields_changed:
            core_payload = self._core_profile_service.update_me(
                user=user,
                name=name,
                preferred_locale=preferred_locale,
                preferred_theme=preferred_theme,
                updated_by=user.id,
            )
            effective_user = user.with_updates(
                name=core_payload.get("name", getattr(user, "name", None)),
                preferred_locale=core_payload.get("preferred_locale", getattr(user, "preferred_locale", None)),
                preferred_theme=core_payload.get("preferred_theme", getattr(user, "preferred_theme", None)),
            )
        if email is not None:
            core_payload = self._core_profile_service.request_email_change(
                user=effective_user,
                new_email=email,
                request_base_url=request_base_url,
                updated_by=user.id,
            )
            effective_user = effective_user.with_updates(
                email=core_payload.get("email", getattr(effective_user, "email", None)),
                pending_email=core_payload.get("pending_email"),
                pending_email_expires_at=core_payload.get("pending_email_expires_at"),
            )
        if app_preferences is not None:
            self._preferences.update_for_user(
                tenant_slug=tenant.slug or "",
                user_id=user.id,
                updates=app_preferences,
            )
        self._core_profile_service.invalidate_cache(tenant.slug, user.id)
        return self.get_profile(user=effective_user, tenant=tenant)

    def update_preferences(self, *, user, tenant, app_preferences: dict[str, object] | None) -> dict[str, object]:
        prefs = self._preferences.update_for_user(
            tenant_slug=tenant.slug or "",
            user_id=user.id,
            updates=app_preferences,
        )
        self._core_profile_service.invalidate_cache(tenant.slug, user.id)
        return build_profile_preferences_response(prefs)


__all__ = ["ProfileFacade"]
