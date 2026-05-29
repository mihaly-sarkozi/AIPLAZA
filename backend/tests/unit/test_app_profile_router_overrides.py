from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.profile.api.router import router
from apps.profile.bootstrap.dependencies import get_profile_facade
from core.modules.users.domain.dto import User
from core.modules.tenant.context.request_tenant_context import RequestTenantContext
from core.modules.tenant.dto import TenantConfig, TenantStatus
from core.kernel.http.tenant_dependencies import require_tenant_context
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


class _FakeFacade:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get_profile(self, *, user, tenant) -> dict[str, object]:
        self.calls.append(("get_profile", {"user": user, "tenant": tenant}))
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
            "tenant_demo_mode": False,
            "tenant_kb_has_training": False,
            "app_preferences": {
                "dashboard_layout": "compact",
                "show_tips": True,
            },
        }

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
        self.calls.append(
            (
                "update_profile",
                {
                    "user": user,
                    "tenant": tenant,
                    "name": name,
                    "email": email,
                    "preferred_locale": preferred_locale,
                    "preferred_theme": preferred_theme,
                    "app_preferences": app_preferences,
                    "request_base_url": request_base_url,
                },
            )
        )
        return {
            "id": user.id,
            "email": user.email,
            "pending_email": email,
            "pending_email_expires_at": None,
            "role": user.role,
            "is_active": user.is_active,
            "name": name,
            "preferred_locale": preferred_locale,
            "preferred_theme": preferred_theme,
            "locale": preferred_locale or "hu",
            "theme": preferred_theme or "light",
            "credentials_password_set": True,
            "tenant_demo_mode": False,
            "tenant_kb_has_training": False,
            "app_preferences": app_preferences or {
                "dashboard_layout": "comfortable",
                "show_tips": True,
            },
        }

    def get_preferences(self, *, user, tenant) -> dict[str, object]:
        self.calls.append(("get_preferences", {"user": user, "tenant": tenant}))
        return {"app_preferences": {"dashboard_layout": "compact", "show_tips": True}}

    def update_preferences(self, *, user, tenant, app_preferences: dict[str, object] | None) -> dict[str, object]:
        self.calls.append(
            ("update_preferences", {"user": user, "tenant": tenant, "app_preferences": app_preferences})
        )
        return {"app_preferences": app_preferences or {"dashboard_layout": "comfortable", "show_tips": True}}


def _user() -> User:
    return User(
        id=1,
        email="profile@example.com",
        password_hash="hash",
        is_active=True,
        role="owner",
        created_at=datetime.now(timezone.utc),
        name="Mihaly",
        preferred_locale="hu",
        preferred_theme="light",
    )


def _tenant() -> RequestTenantContext:
    return RequestTenantContext(
        tenant_id=21,
        slug="misi",
        name="Misi",
        created_at=datetime.now(timezone.utc),
        status=TenantStatus(tenant_id=21, slug="misi", is_active=True),
        config=TenantConfig(tenant_id=21, slug="misi", package="free", feature_flags={}, limits={}),
        domain=None,
        correlation_id="corr-1",
        security_version=0,
    )


def _app(*, facade: _FakeFacade, current_user: User | None) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[require_tenant_context] = lambda: _tenant()
    app.dependency_overrides[get_profile_facade] = lambda: facade
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    return app


def test_profile_router_can_use_fake_dependency_overrides() -> None:
    facade = _FakeFacade()
    app = _app(facade=facade, current_user=_user())

    with TestClient(app, base_url="http://misi.lvh.me") as client:
        response = client.patch(
            "/api/profile",
            json={
                "name": "Uj Mihaly",
                "preferred_locale": "en",
                "preferred_theme": "dark",
                "app_preferences": {
                    "dashboard_layout": "compact",
                    "show_tips": False,
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Uj Mihaly"
    assert payload["app_preferences"]["dashboard_layout"] == "compact"
    assert facade.calls[-1][0] == "update_profile"
    assert facade.calls[-1][1]["app_preferences"] == {
        "dashboard_layout": "compact",
        "show_tips": False,
    }


def test_profile_router_returns_401_without_current_user_override() -> None:
    app = _app(facade=_FakeFacade(), current_user=None)

    with TestClient(app, base_url="http://misi.lvh.me") as client:
        response = client.get("/api/profile")

    assert response.status_code == 401


def test_get_profile_preferences_returns_success_shape() -> None:
    app = _app(facade=_FakeFacade(), current_user=_user())

    with TestClient(app, base_url="http://misi.lvh.me") as client:
        response = client.get("/api/profile/preferences")

    assert response.status_code == 200
    assert response.json() == {
        "app_preferences": {
            "dashboard_layout": "compact",
            "show_tips": True,
        }
    }


def test_patch_profile_preferences_passes_only_app_preferences_to_facade() -> None:
    facade = _FakeFacade()
    app = _app(facade=facade, current_user=_user())

    with TestClient(app, base_url="http://misi.lvh.me") as client:
        response = client.patch(
            "/api/profile/preferences",
            json={"dashboard_layout": "compact", "show_tips": False},
        )

    assert response.status_code == 200
    assert response.json() == {
        "app_preferences": {
            "dashboard_layout": "compact",
            "show_tips": False,
        }
    }
    assert facade.calls[-1][0] == "update_preferences"
    assert facade.calls[-1][1]["app_preferences"] == {
        "dashboard_layout": "compact",
        "show_tips": False,
    }
