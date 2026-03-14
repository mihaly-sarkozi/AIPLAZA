# tests/integration/test_registration.py
"""Regisztráció (set-password link) tesztek: token validálás és jelszó beállítás auth nélkül (a link token a hitelesítés)."""
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


def test_validate_set_password_invalid_token_returns_400(client_superuser: TestClient, mock_user_service):
    """GET /users/set-password/validate invalid token → 400 (auth nem kell a végponthoz)."""
    mock_user_service.validate_invite_token.return_value = "invalid"
    r = client_superuser.get("/api/users/set-password/validate", params={"token": "any"})
    assert r.status_code == 400


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
    """GET /users/set-password/validate?token=good → 200, valid: true (auth nem kell)."""
    mock_user_service.validate_invite_token.return_value = "valid"
    r = client_superuser.get("/api/users/set-password/validate", params={"token": "good"})
    assert r.status_code == 200
    assert r.json().get("valid") is True


def test_set_password_invalid_token_returns_400(client_superuser: TestClient, mock_user_service):
    """POST /users/set-password invalid token → 400 (auth nem kell)."""
    mock_user_service.set_password.side_effect = ValueError("invalid_token")
    r = client_superuser.post(
        "/api/users/set-password",
        json={"token": "t", "password": "SecureP@ss1"},
    )
    assert r.status_code == 400


def test_set_password_success(client_superuser: TestClient, mock_user_service):
    """POST /users/set-password érvényes token + jelszó → 200 (auth nem kell)."""
    r = client_superuser.post(
        "/api/users/set-password",
        json={"token": "valid-token-123", "password": "SecureP@ss1"},
    )
    assert r.status_code == 200
    assert "message" in r.json() or "Jelszó" in str(r.json())


def test_set_password_invalid_token_returns_400_detail(client_superuser: TestClient, mock_user_service):
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
