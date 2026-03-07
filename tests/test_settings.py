# tests/test_settings.py
"""Settings modul tesztek: GET/PATCH /settings (csak owner)."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from main import app
from apps.core.di import get_settings_service
from apps.core.security.auth_dependencies import get_current_user
from apps.users.domain.user import User


def test_get_settings_without_auth_returns_401(client: TestClient):
    """GET /settings auth nélkül → 401."""
    r = client.get("/api/settings")
    assert r.status_code == 401


def test_get_settings_non_owner_returns_403(client: TestClient, mock_settings_service):
    """GET /settings user/admin role-lal (nem owner) → 403."""
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


def test_get_settings_success(client_authenticated: TestClient, mock_settings_service):
    """GET /settings ownerrel → 200, two_factor_enabled."""
    app.dependency_overrides[get_settings_service] = lambda: mock_settings_service
    try:
        r = client_authenticated.get("/api/settings")
        assert r.status_code == 200
        data = r.json()
        assert "two_factor_enabled" in data
        assert data["two_factor_enabled"] is False
    finally:
        app.dependency_overrides.pop(get_settings_service, None)


def test_patch_settings_without_auth_returns_401(client: TestClient):
    """PATCH /settings auth nélkül → 401."""
    r = client.patch("/api/settings", json={"two_factor_enabled": True})
    assert r.status_code == 401


def test_patch_settings_non_owner_returns_403(client: TestClient, mock_settings_service):
    """PATCH /settings nem ownerrel → 403."""
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


def test_patch_settings_success(client_authenticated: TestClient, mock_settings_service):
    """PATCH /settings ownerrel → 200, two_factor_enabled frissítve."""
    mock_settings_service.is_two_factor_enabled.return_value = True
    app.dependency_overrides[get_settings_service] = lambda: mock_settings_service
    try:
        r = client_authenticated.patch("/api/settings", json={"two_factor_enabled": True})
        assert r.status_code == 200
        data = r.json()
        assert data["two_factor_enabled"] is True
        mock_settings_service.set_two_factor_enabled.assert_called_once_with(True, updated_by=1)
    finally:
        app.dependency_overrides.pop(get_settings_service, None)
