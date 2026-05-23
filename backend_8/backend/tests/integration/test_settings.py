"""Settings modul tesztek: GET/PATCH /settings (csak owner)."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from core.modules.users.domain.dto import User  # lightweight dataclass

pytestmark = pytest.mark.integration


def test_get_settings_without_auth_returns_401(client: TestClient):
    """GET /settings auth nélkül → 401."""
    r = client.get("/api/settings")
    assert r.status_code == 401


def test_get_settings_non_owner_returns_403(client: TestClient, mock_settings_service, app):
    """GET /settings user/admin role-lal (nem owner) → 403."""
    from apps.settings.dependencies import get_settings_service
    from core.modules.auth.web.dependencies.auth_dependencies import get_current_user
    app.dependency_overrides[get_settings_service] = lambda: mock_settings_service
    non_owner = User(
        id=2,
        email="admin@example.com",
        password_hash="",
        is_active=True,
        role="admin",
        created_at=datetime.now(timezone.utc),
    )
    app.dependency_overrides[get_current_user] = lambda: non_owner
    try:
        r = client.get("/api/settings")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_settings_service, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_get_settings_success(client_authenticated: TestClient, mock_settings_service, app):
    """GET /settings ownerrel → 200, teljes settings payload."""
    from apps.settings.dependencies import get_settings_service
    from core.kernel.deps.facade import get_permission_service

    get_permission_service().register_permissions(("settings.read", "settings.write"))
    app.dependency_overrides[get_settings_service] = lambda: mock_settings_service
    try:
        r = client_authenticated.get("/api/settings")
        assert r.status_code == 200
        data = r.json()
        assert "two_factor_enabled" in data
        assert data["two_factor_enabled"] is False
        assert data["timezone"] == "UTC"
        assert data["date_format"] == "YYYY-MM-DD"
        assert data["time_format"] == "HH:mm"
    finally:
        app.dependency_overrides.pop(get_settings_service, None)


def test_patch_settings_without_auth_returns_401(client: TestClient):
    """PATCH /settings auth nélkül → 401."""
    r = client.patch("/api/settings", json={"two_factor_enabled": True})
    assert r.status_code == 401


def test_patch_settings_non_owner_returns_403(client: TestClient, mock_settings_service, app):
    """PATCH /settings nem ownerrel → 403."""
    from apps.settings.dependencies import get_settings_service
    from core.modules.auth.web.dependencies.auth_dependencies import get_current_user
    app.dependency_overrides[get_settings_service] = lambda: mock_settings_service
    non_owner = User(
        id=2,
        email="u@example.com",
        password_hash="",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    app.dependency_overrides[get_current_user] = lambda: non_owner
    try:
        r = client.patch("/api/settings", json={"two_factor_enabled": True})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_settings_service, None)
        app.dependency_overrides.pop(get_current_user, None)


def test_patch_settings_success(client_authenticated: TestClient, mock_settings_service, app):
    """PATCH /settings ownerrel → 200, részleges settings update."""
    from apps.settings.dependencies import get_settings_service
    from core.kernel.deps.facade import get_permission_service

    get_permission_service().register_permissions(("settings.read", "settings.write"))
    app.dependency_overrides[get_settings_service] = lambda: mock_settings_service
    try:
        r = client_authenticated.patch(
            "/api/settings",
            json={
                "two_factor_enabled": True,
                "timezone": "Europe/Budapest",
                "date_format": "DD.MM.YYYY",
                "time_format": "HH:mm:ss",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["two_factor_enabled"] is True
        assert data["timezone"] == "Europe/Budapest"
        assert data["date_format"] == "DD.MM.YYYY"
        assert data["time_format"] == "HH:mm:ss"
        mock_settings_service.update_settings.assert_called_once_with(
            two_factor_enabled=True,
            timezone="Europe/Budapest",
            date_format="DD.MM.YYYY",
            time_format="HH:mm:ss",
            billing_company_name=None,
            billing_tax_id=None,
            billing_address_line=None,
            billing_postal_code=None,
            billing_city=None,
            billing_region=None,
            billing_country=None,
            updated_by=1,
        )
    finally:
        app.dependency_overrides.pop(get_settings_service, None)
