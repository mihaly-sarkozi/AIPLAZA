# tests/test_registration.py
"""Regisztráció (set-password link) tesztek: token validálás, jelszó beállítás. Admin/owner kötelező."""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from main import app
from apps.core.security.auth_dependencies import get_current_user
from apps.users.domain.user import User


def test_validate_set_password_without_auth_returns_401(client: TestClient):
    """GET /users/set-password/validate auth nélkül → 401."""
    r = client.get("/api/users/set-password/validate", params={"token": "any"})
    assert r.status_code == 401


def test_validate_set_password_token_missing_returns_400(client_superuser: TestClient, mock_user_service):
    """GET /users/set-password/validate token nélkül → 400 (invalid)."""
    r = client_superuser.get("/api/users/set-password/validate")
    assert r.status_code == 400
    data = r.json().get("detail", r.json())
    assert data.get("valid") is False or "valid" in str(data).lower()


def test_validate_set_password_token_invalid_returns_400(client_superuser: TestClient, mock_user_service):
    """GET /users/set-password/validate?token=bad → 400 invalid."""
    mock_user_service.validate_invite_token.return_value = "invalid"
    r = client_superuser.get("/api/users/set-password/validate", params={"token": "bad"})
    assert r.status_code == 400


def test_validate_set_password_token_expired_returns_410(client_superuser: TestClient, mock_user_service):
    """GET /users/set-password/validate?token=expired → 410."""
    mock_user_service.validate_invite_token.return_value = "expired"
    r = client_superuser.get("/api/users/set-password/validate", params={"token": "expired"})
    assert r.status_code == 410
    data = r.json().get("detail", {})
    assert data.get("reason") == "expired" or "expired" in str(data).lower()


def test_validate_set_password_token_valid_returns_200(client_superuser: TestClient, mock_user_service):
    """GET /users/set-password/validate?token=good → 200, valid: true."""
    mock_user_service.validate_invite_token.return_value = "valid"
    r = client_superuser.get("/api/users/set-password/validate", params={"token": "good"})
    assert r.status_code == 200
    assert r.json().get("valid") is True


def test_set_password_without_auth_returns_401(client: TestClient):
    """POST /users/set-password auth nélkül → 401."""
    r = client.post(
        "/api/users/set-password",
        json={"token": "t", "password": "SecureP@ss1"},
    )
    assert r.status_code == 401


def test_set_password_success(client_superuser: TestClient, mock_user_service):
    """POST /users/set-password érvényes token + jelszó → 200."""
    r = client_superuser.post(
        "/api/users/set-password",
        json={"token": "valid-token-123", "password": "SecureP@ss1"},
    )
    assert r.status_code == 200
    assert "message" in r.json() or "Jelszó" in str(r.json())


def test_set_password_invalid_token_returns_400(client_superuser: TestClient, mock_user_service):
    """POST /users/set-password érvénytelen token → 400."""
    mock_user_service.set_password.side_effect = ValueError("invalid_token")
    r = client_superuser.post(
        "/api/users/set-password",
        json={"token": "invalid", "password": "SecureP@ss1"},
    )
    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert detail.get("reason") == "invalid" or "invalid" in str(detail).lower()


def test_set_password_expired_token_returns_410(client_superuser: TestClient, mock_user_service):
    """POST /users/set-password lejárt token → 410."""
    mock_user_service.set_password.side_effect = ValueError("token_expired")
    r = client_superuser.post(
        "/api/users/set-password",
        json={"token": "expired", "password": "SecureP@ss1"},
    )
    assert r.status_code == 410
    detail = r.json().get("detail", {})
    assert detail.get("reason") == "expired"


def test_set_password_non_admin_returns_403(client_superuser: TestClient):
    """POST /users/set-password user role-lal (nem admin/owner) → 403."""
    non_admin = User(
        id=2,
        email="user@example.com",
        password_hash="",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    app.dependency_overrides[get_current_user] = lambda: non_admin
    try:
        r = client_superuser.post(
            "/api/users/set-password",
            json={"token": "t", "password": "SecureP@ss1"},
        )
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
