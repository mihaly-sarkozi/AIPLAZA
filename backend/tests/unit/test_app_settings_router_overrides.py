from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from apps.settings.api.router import router
from apps.settings.bootstrap.dependencies import get_settings_facade
from core.modules.users.domain.dto import User
from core.modules.auth.web.dependencies import auth_dependencies
from core.modules.auth.web.dependencies.auth_dependencies import get_current_user

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]

BILLING_DEFAULTS = {
    "billing_company_name": "",
    "billing_tax_id": "",
    "billing_address_line": "",
    "billing_postal_code": "",
    "billing_city": "",
    "billing_region": "",
    "billing_country": "",
    "billing_customer_type": "company",
    "billing_full_name": "",
}


class _FakeSettingsFacade:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.sections: list[dict[str, object]] = [
            {
                "key": "core.system",
                "label": "Core rendszer",
                "path": "/admin/settings?section=core.system",
                "permission": "settings.read",
                "order": 10,
                "description": "Felhasználók, hitelesítés és rendszerbeállítások.",
                "source": "core",
            }
        ]

    def get_settings(self) -> dict[str, object]:
        self.calls.append(("get_settings", {}))
        return {
            "two_factor_enabled": False,
            "timezone": "UTC",
            "date_format": "YYYY-MM-DD",
            "time_format": "HH:mm",
        }

    def get_two_factor_settings(self) -> dict[str, object]:
        self.calls.append(("get_two_factor_settings", {}))
        return {"two_factor_enabled": False}

    def update_two_factor_settings(
        self,
        *,
        two_factor_enabled: bool | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "update_two_factor_settings",
                {"two_factor_enabled": two_factor_enabled, "updated_by": updated_by},
            )
        )
        return {"two_factor_enabled": bool(two_factor_enabled)}

    def get_locale_settings(self) -> dict[str, object]:
        self.calls.append(("get_locale_settings", {}))
        return {"timezone": "UTC", "date_format": "YYYY-MM-DD", "time_format": "HH:mm"}

    def update_locale_settings(
        self,
        *,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "update_locale_settings",
                {
                    "timezone": timezone,
                    "date_format": date_format,
                    "time_format": time_format,
                    "updated_by": updated_by,
                },
            )
        )
        return {
            "timezone": timezone or "UTC",
            "date_format": date_format or "YYYY-MM-DD",
            "time_format": time_format or "HH:mm",
        }

    def get_billing_settings(self) -> dict[str, object]:
        self.calls.append(("get_billing_settings", {}))
        return dict(BILLING_DEFAULTS)

    def update_billing_settings(
        self,
        *,
        billing_company_name: str | None = None,
        billing_tax_id: str | None = None,
        billing_address_line: str | None = None,
        billing_postal_code: str | None = None,
        billing_city: str | None = None,
        billing_region: str | None = None,
        billing_country: str | None = None,
        billing_customer_type: str | None = None,
        billing_full_name: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "update_billing_settings",
                {
                    "billing_company_name": billing_company_name,
                    "billing_tax_id": billing_tax_id,
                    "billing_address_line": billing_address_line,
                    "billing_postal_code": billing_postal_code,
                    "billing_city": billing_city,
                    "billing_region": billing_region,
                    "billing_country": billing_country,
                    "billing_customer_type": billing_customer_type,
                    "billing_full_name": billing_full_name,
                    "updated_by": updated_by,
                },
            )
        )
        return {
            "billing_customer_type": billing_customer_type or "company",
            "billing_full_name": billing_full_name or "",
            "billing_company_name": billing_company_name or "",
            "billing_tax_id": billing_tax_id or "",
            "billing_address_line": billing_address_line or "",
            "billing_postal_code": billing_postal_code or "",
            "billing_city": billing_city or "",
            "billing_region": billing_region or "",
            "billing_country": billing_country or "",
        }

    def update_settings(
        self,
        *,
        two_factor_enabled: bool | None = None,
        timezone: str | None = None,
        date_format: str | None = None,
        time_format: str | None = None,
        billing_company_name: str | None = None,
        billing_tax_id: str | None = None,
        billing_address_line: str | None = None,
        billing_postal_code: str | None = None,
        billing_city: str | None = None,
        billing_region: str | None = None,
        billing_country: str | None = None,
        billing_customer_type: str | None = None,
        billing_full_name: str | None = None,
        updated_by: int | None = None,
    ) -> dict[str, object]:
        self.calls.append(
            (
                "update_settings",
                {
                    "two_factor_enabled": two_factor_enabled,
                    "timezone": timezone,
                    "date_format": date_format,
                    "time_format": time_format,
                    "billing_company_name": billing_company_name,
                    "billing_tax_id": billing_tax_id,
                    "billing_address_line": billing_address_line,
                    "billing_postal_code": billing_postal_code,
                    "billing_city": billing_city,
                    "billing_region": billing_region,
                    "billing_country": billing_country,
                    "billing_customer_type": billing_customer_type,
                    "billing_full_name": billing_full_name,
                    "updated_by": updated_by,
                },
            )
        )
        return {
            "two_factor_enabled": bool(two_factor_enabled),
            "timezone": timezone or "UTC",
            "date_format": date_format or "YYYY-MM-DD",
            "time_format": time_format or "HH:mm",
                "billing_customer_type": billing_customer_type or "company",
                "billing_full_name": billing_full_name or "",
                "billing_company_name": billing_company_name or "",
                "billing_tax_id": billing_tax_id or "",
                "billing_address_line": billing_address_line or "",
                "billing_postal_code": billing_postal_code or "",
                "billing_city": billing_city or "",
                "billing_region": billing_region or "",
                "billing_country": billing_country or "",
        }

    def get_sections(self) -> list[dict[str, object]]:
        self.calls.append(("get_sections", {}))
        return list(self.sections)


def _user() -> User:
    return User(
        id=1,
        email="owner@example.com",
        password_hash="hash",
        is_active=True,
        role="owner",
        created_at=datetime.now(timezone.utc),
    )


def _app(
    *,
    facade: _FakeSettingsFacade,
    current_user: User | None,
    monkeypatch: pytest.MonkeyPatch,
    permission_allowed: bool = True,
) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_settings_facade] = lambda: facade
    if current_user is not None:
        app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        auth_dependencies,
        "_authorization_policy",
        lambda: SimpleNamespace(ensure_permission=lambda user, permission: SimpleNamespace(allowed=permission_allowed)),
    )
    return app


def _get_route(path: str, method: str) -> APIRoute:
    for route in router.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise AssertionError(f"Route not found: {method} {path}")


def test_get_settings_returns_success_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(facade=_FakeSettingsFacade(), current_user=_user(), monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.get("/api/settings")

    assert response.status_code == 200
    assert response.json() == {
        "two_factor_enabled": False,
        "timezone": "UTC",
        "date_format": "YYYY-MM-DD",
        "time_format": "HH:mm",
        **BILLING_DEFAULTS,
    }


def test_patch_settings_delegates_to_facade(monkeypatch: pytest.MonkeyPatch) -> None:
    facade = _FakeSettingsFacade()
    app = _app(facade=facade, current_user=_user(), monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.patch(
            "/api/settings",
            json={
                "two_factor_enabled": True,
                "timezone": "Europe/Budapest",
                "date_format": "DD.MM.YYYY",
                "time_format": "HH:mm:ss",
            },
        )

    assert response.status_code == 200
    assert response.json()["timezone"] == "Europe/Budapest"
    assert facade.calls[-1] == (
        "update_settings",
        {
            "two_factor_enabled": True,
            "timezone": "Europe/Budapest",
            "date_format": "DD.MM.YYYY",
            "time_format": "HH:mm:ss",
            "billing_company_name": None,
            "billing_tax_id": None,
            "billing_address_line": None,
            "billing_postal_code": None,
            "billing_city": None,
            "billing_region": None,
            "billing_country": None,
            "billing_customer_type": None,
            "billing_full_name": None,
            "updated_by": 1,
        },
    )


def test_split_locale_settings_delegates_to_facade(monkeypatch: pytest.MonkeyPatch) -> None:
    facade = _FakeSettingsFacade()
    app = _app(facade=facade, current_user=_user(), monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.patch(
            "/api/settings/locale",
            json={"timezone": "Europe/Budapest", "date_format": "DD.MM.YYYY", "time_format": "HH:mm:ss"},
        )

    assert response.status_code == 200
    assert facade.calls[-1] == (
        "update_locale_settings",
        {
            "timezone": "Europe/Budapest",
            "date_format": "DD.MM.YYYY",
            "time_format": "HH:mm:ss",
            "updated_by": 1,
        },
    )


def test_split_two_factor_settings_delegates_to_facade(monkeypatch: pytest.MonkeyPatch) -> None:
    facade = _FakeSettingsFacade()
    app = _app(facade=facade, current_user=_user(), monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.patch("/api/settings/security/2fa", json={"two_factor_enabled": True})

    assert response.status_code == 200
    assert facade.calls[-1] == (
        "update_two_factor_settings",
        {"two_factor_enabled": True, "updated_by": 1},
    )


def test_split_billing_settings_delegates_to_facade(monkeypatch: pytest.MonkeyPatch) -> None:
    facade = _FakeSettingsFacade()
    app = _app(facade=facade, current_user=_user(), monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.patch(
            "/api/settings/billing",
            json={
                "billing_customer_type": "company",
                "billing_company_name": "Example Kft.",
                "billing_tax_id": "HU12345678",
                "billing_address_line": "Fo utca 1.",
                "billing_postal_code": "1051",
                "billing_city": "Budapest",
                "billing_country": "HU",
            },
        )

    assert response.status_code == 200
    assert facade.calls[-1] == (
        "update_billing_settings",
        {
            "billing_company_name": "Example Kft.",
            "billing_tax_id": "HU12345678",
            "billing_address_line": "Fo utca 1.",
            "billing_postal_code": "1051",
            "billing_city": "Budapest",
            "billing_region": None,
            "billing_country": "HU",
            "billing_customer_type": "company",
            "billing_full_name": None,
            "updated_by": 1,
        },
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timezone", "Mars/Olympus"),
        ("date_format", "YYYY/DD/MM"),
        ("time_format", "24h"),
    ],
)
def test_patch_settings_rejects_invalid_literal_values(
    field: str,
    value: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade = _FakeSettingsFacade()
    app = _app(facade=facade, current_user=_user(), monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.patch("/api/settings", json={field: value})

    assert response.status_code == 422
    assert all(call[0] != "update_settings" for call in facade.calls)


@pytest.mark.parametrize(
    ("payload", "expected_error_type"),
    [
        ({"unexpected_admin_override": True}, "extra_forbidden"),
        ({"two_factor_enabled": "true"}, "bool_type"),
        ({"billing_company_name": 123}, "string_type"),
        (["not", "an", "object"], "model_attributes_type"),
    ],
)
def test_patch_settings_rejects_malformed_or_manipulated_payloads(
    payload,
    expected_error_type: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    facade = _FakeSettingsFacade()
    app = _app(facade=facade, current_user=_user(), monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.patch("/api/settings", json=payload)

    assert response.status_code == 422
    assert expected_error_type in {error["type"] for error in response.json()["detail"]}
    assert all(call[0] != "update_settings" for call in facade.calls)


def test_patch_settings_accepts_empty_body_as_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    facade = _FakeSettingsFacade()
    app = _app(facade=facade, current_user=_user(), monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.patch("/api/settings", json={})

    assert response.status_code == 200
    assert facade.calls[-1] == (
        "update_settings",
        {
            "two_factor_enabled": None,
            "timezone": None,
            "date_format": None,
            "time_format": None,
            "billing_company_name": None,
            "billing_tax_id": None,
            "billing_address_line": None,
            "billing_postal_code": None,
            "billing_city": None,
            "billing_region": None,
            "billing_country": None,
            "billing_customer_type": None,
            "billing_full_name": None,
            "updated_by": 1,
        },
    )


def test_get_settings_sections_returns_facade_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(facade=_FakeSettingsFacade(), current_user=_user(), monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.get("/api/settings/sections")

    assert response.status_code == 200
    assert response.json()[0]["key"] == "core.system"


def test_get_settings_sections_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    facade = _FakeSettingsFacade()
    facade.sections = []
    app = _app(facade=facade, current_user=_user(), monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.get("/api/settings/sections")

    assert response.status_code == 200
    assert response.json() == []


def test_get_settings_sections_requires_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(facade=_FakeSettingsFacade(), current_user=None, monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.get("/api/settings/sections")

    assert response.status_code == 401


def test_get_settings_sections_requires_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(
        facade=_FakeSettingsFacade(),
        current_user=_user(),
        monkeypatch=monkeypatch,
        permission_allowed=False,
    )

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.get("/api/settings/sections")

    assert response.status_code == 403
    assert response.json()["detail"] == "Missing permission: settings.read"


def test_patch_settings_uses_body_not_query_param() -> None:
    route = _get_route("/settings", "PATCH")

    query_param_names = {param.name for param in route.dependant.query_params}
    body_param_names = {param.name for param in route.dependant.body_params}

    assert "body" not in query_param_names
    assert "body" in body_param_names


def test_patch_split_billing_settings_rejects_non_admin_owner_role(monkeypatch: pytest.MonkeyPatch) -> None:
    facade = _FakeSettingsFacade()
    member = User(
        id=3,
        email="member@example.com",
        password_hash="hash",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    app = _app(facade=facade, current_user=member, monkeypatch=monkeypatch)

    with TestClient(app, base_url="http://demo.lvh.me") as client:
        response = client.patch(
            "/api/settings/billing",
            json={
                "billing_customer_type": "company",
                "billing_company_name": "Example Kft.",
                "billing_tax_id": "HU12345678",
                "billing_address_line": "Fo utca 1.",
                "billing_postal_code": "1051",
                "billing_city": "Budapest",
                "billing_country": "HU",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Only owner or admin can update billing settings."
