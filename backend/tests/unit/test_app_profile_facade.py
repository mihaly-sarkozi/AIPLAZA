from __future__ import annotations

from datetime import datetime, timezone

import pytest

from apps.profile.service.profile_facade import ProfileFacade
from core.modules.users.domain.dto import User
from core.modules.tenant.context.request_tenant_context import RequestTenantContext
from core.modules.tenant.dto import TenantConfig, TenantStatus

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _CoreProfileService:
    def __init__(self) -> None:
        self.updated_payload: dict[str, object] | None = None
        self.update_calls = 0
        self.invalidations: list[tuple[str | None, int]] = []

    def get_me(self, *, user, tenant, training_status_reader=None) -> dict[str, object]:
        return {
            "id": user.id,
            "email": user.email,
            "pending_email": getattr(user, "pending_email", None),
            "pending_email_expires_at": getattr(user, "pending_email_expires_at", None),
            "role": user.role,
            "is_active": user.is_active,
            "name": user.name,
            "preferred_locale": user.preferred_locale,
            "preferred_theme": user.preferred_theme,
            "locale": user.preferred_locale or "hu",
            "theme": user.preferred_theme or "light",
            "credentials_password_set": True,
            "tenant_demo_mode": True,
            "tenant_kb_has_training": True,
        }

    def update_me(self, *, user, name, preferred_locale, preferred_theme, updated_by=None) -> dict[str, object]:
        self.update_calls += 1
        self.updated_payload = {
            "name": name,
            "preferred_locale": preferred_locale,
            "preferred_theme": preferred_theme,
            "updated_by": updated_by,
        }
        updated_user = user.with_updates(
            name=name if name is not None else user.name,
            preferred_locale=preferred_locale,
            preferred_theme=preferred_theme,
        )
        return self.get_me(user=updated_user, tenant=None)

    def request_email_change(self, *, user, new_email, request_base_url, updated_by=None) -> dict[str, object]:
        if getattr(user, "role", None) == "owner":
            return self.get_me(user=user.with_updates(pending_email=new_email), tenant=None)
        return self.get_me(user=user.with_updates(email=new_email, pending_email=None), tenant=None)

    def invalidate_cache(self, tenant_slug: str | None, user_id: int) -> None:
        self.invalidations.append((tenant_slug, user_id))


class _PreferencesService:
    def __init__(self) -> None:
        self.dashboard_layout = "comfortable"
        self.show_tips = True
        self.update_calls = 0

    def get_for_user(self, *, tenant_slug: str, user_id: int):
        return type(
            "Prefs",
            (),
            {
                "dashboard_layout": self.dashboard_layout,
                "show_tips": self.show_tips,
            },
        )()

    def update_for_user(self, *, tenant_slug: str, user_id: int, updates: dict[str, object] | None):
        self.update_calls += 1
        if updates and "dashboard_layout" in updates:
            self.dashboard_layout = str(updates["dashboard_layout"])
        if updates and "show_tips" in updates:
            self.show_tips = bool(updates["show_tips"])
        return self.get_for_user(tenant_slug=tenant_slug, user_id=user_id)


def _tenant_context() -> RequestTenantContext:
    return RequestTenantContext(
        tenant_id=7,
        slug="demo_tenant",
        name="Demo Tenant",
        created_at=datetime.now(timezone.utc),
        status=TenantStatus(tenant_id=7, slug="demo_tenant", is_active=True),
        config=TenantConfig(
            tenant_id=7,
            slug="demo_tenant",
            package="free",
            feature_flags={"demo_mode": True},
            limits={},
        ),
        domain=None,
        correlation_id="corr-1",
        security_version=0,
    )


def _user() -> User:
    return User(
        id=11,
        email="profile@example.com",
        password_hash="hash",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
        name="Teszt Elek",
        preferred_locale="hu",
        preferred_theme="light",
    )


def test_get_profile_combines_core_payload_with_app_preferences() -> None:
    facade = ProfileFacade(
        core_profile_service=_CoreProfileService(),
        preferences_service=_PreferencesService(),
    )

    payload = facade.get_profile(user=_user(), tenant=_tenant_context())

    assert payload["email"] == "profile@example.com"
    assert payload["app_preferences"] == {
        "dashboard_layout": "comfortable",
        "show_tips": True,
    }


def test_update_profile_updates_core_fields_and_preferences() -> None:
    core_service = _CoreProfileService()
    prefs_service = _PreferencesService()
    facade = ProfileFacade(
        core_profile_service=core_service,
        preferences_service=prefs_service,
    )

    payload = facade.update_profile(
        user=_user(),
        tenant=_tenant_context(),
        name="  Uj Nev  ",
        email=None,
        preferred_locale="en",
        preferred_theme="dark",
        app_preferences={"dashboard_layout": "compact", "show_tips": False},
    )

    assert core_service.updated_payload == {
        "name": "  Uj Nev  ",
        "preferred_locale": "en",
        "preferred_theme": "dark",
        "updated_by": 11,
    }
    assert payload["name"] == "  Uj Nev  "
    assert payload["locale"] == "en"
    assert payload["theme"] == "dark"
    assert payload["app_preferences"] == {
        "dashboard_layout": "compact",
        "show_tips": False,
    }
    assert core_service.invalidations == [("demo_tenant", 11)]


def test_update_profile_with_only_app_preferences_skips_core_update() -> None:
    core_service = _CoreProfileService()
    prefs_service = _PreferencesService()
    facade = ProfileFacade(
        core_profile_service=core_service,
        preferences_service=prefs_service,
    )

    payload = facade.update_profile(
        user=_user(),
        tenant=_tenant_context(),
        name=None,
        email=None,
        preferred_locale=None,
        preferred_theme=None,
        app_preferences={"dashboard_layout": "compact"},
    )

    assert core_service.update_calls == 0
    assert prefs_service.update_calls == 1
    assert payload["app_preferences"]["dashboard_layout"] == "compact"


def test_update_profile_with_only_core_fields_skips_preference_write() -> None:
    core_service = _CoreProfileService()
    prefs_service = _PreferencesService()
    facade = ProfileFacade(
        core_profile_service=core_service,
        preferences_service=prefs_service,
    )

    payload = facade.update_profile(
        user=_user(),
        tenant=_tenant_context(),
        name="Only Core",
        email=None,
        preferred_locale="en",
        preferred_theme="dark",
        app_preferences=None,
    )

    assert core_service.update_calls == 1
    assert prefs_service.update_calls == 0
    assert payload["name"] == "Only Core"
    assert payload["locale"] == "en"


def test_update_profile_email_change_returns_new_email_for_non_owner() -> None:
    facade = ProfileFacade(
        core_profile_service=_CoreProfileService(),
        preferences_service=_PreferencesService(),
    )

    payload = facade.update_profile(
        user=_user(),
        tenant=_tenant_context(),
        name=None,
        email="new-profile@example.com",
        preferred_locale=None,
        preferred_theme=None,
        app_preferences=None,
    )

    assert payload["email"] == "new-profile@example.com"
    assert payload["pending_email"] is None
