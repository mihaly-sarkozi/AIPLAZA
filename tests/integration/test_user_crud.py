# tests/integration/test_user_crud.py
"""User CRUD és resend-invite végpont tesztek (superuser kell)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from apps.users.domain.user import User

pytestmark = pytest.mark.integration


@pytest.mark.smoke_only
def test_list_users_success_returns_list(client_superuser: TestClient, mock_user_service):
    """GET /users superuserral → 200, lista (akár üres); minden elem dict id vagy email mezővel."""
    mock_user_service.list_all.return_value = []
    r = client_superuser.get("/api/users")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list), "Response must be a list"
    for item in data:
        assert isinstance(item, dict), "Each item must be a dict"
        assert "id" in item or "email" in item, "Each item must have id or email"


def test_list_users_with_users_returns_data(client_superuser: TestClient, mock_user_service, sample_user):
    """GET /users ha van user → 200, lista nem üres."""
    mock_user_service.list_all.return_value = [sample_user]
    r = client_superuser.get("/api/users")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["email"] == sample_user.email
    assert data[0]["id"] == sample_user.id
    assert "password_hash" not in data[0]


def test_list_users_non_superuser_returns_403(client_superuser: TestClient):
    """GET /users nem superuserrel → 403."""
    from tests.conftest import get_app
    from apps.core.security.auth_dependencies import get_current_user
    app = get_app()
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
        r = client_superuser.get("/api/users")
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_get_user_success(client_superuser: TestClient, mock_user_service, sample_user):
    """GET /users/1 → 200, user adatok."""
    r = client_superuser.get("/api/users/1")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == 1
    assert data["email"] == sample_user.email
    assert "password_hash" not in data


def test_get_user_not_found_returns_404(client_superuser: TestClient, mock_user_service):
    """GET /users/999 ha nincs ilyen user → 404."""
    mock_user_service.get_by_id.side_effect = lambda uid: None
    r = client_superuser.get("/api/users/999")
    assert r.status_code == 404


def test_create_user_success(client_superuser: TestClient, mock_user_service):
    """POST /users érvényes body → 201/200, user vissza (pending_registration)."""
    mock_user_service.create.return_value = User(
        id=2,
        email="newuser@example.com",
        password_hash="",
        is_active=False,
        role="user",
        created_at=datetime.now(timezone.utc),
        name="New User",
    )
    r = client_superuser.post(
        "/api/users",
        json={"email": "newuser@example.com", "name": "New User", "role": "user"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "newuser@example.com"
    assert data["id"] == 2
    assert data.get("pending_registration") is True


def test_create_user_duplicate_email_returns_400(client_superuser: TestClient, mock_user_service):
    """POST /users ha az email már létezik → 400."""
    mock_user_service.create.side_effect = ValueError("Email already exists")
    r = client_superuser.post(
        "/api/users",
        json={"email": "existing@example.com", "name": "", "role": "user"},
    )
    assert r.status_code == 400


def test_update_user_success(client_superuser: TestClient, mock_user_service):
    """PUT /users/2 name + is_active → 200, frissített user."""
    mock_user_service.update.return_value = User(
        id=2,
        email="u@example.com",
        password_hash="",
        is_active=False,
        role="user",
        created_at=datetime.now(timezone.utc),
        name="Updated Name",
    )
    r = client_superuser.put(
        "/api/users/2",
        json={"name": "Updated Name", "is_active": False},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Updated Name"
    assert data["is_active"] is False


def test_update_owner_is_active_returns_400(client_superuser: TestClient, mock_user_service):
    """PUT /users/1 (owner) is_active módosítás → 400 (owner aktív státusza nem módosítható)."""
    mock_user_service.update.side_effect = ValueError("Owner aktív státusza nem módosítható.")
    r = client_superuser.put("/api/users/1", json={"name": "Other", "is_active": True})
    assert r.status_code == 400


def test_delete_user_success(client_superuser: TestClient, mock_user_service):
    """DELETE /users/2 (nem saját magad) → 200, ok."""
    r = client_superuser.delete("/api/users/2")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok" or "message" in data


def test_delete_self_returns_400(client_superuser: TestClient, mock_user_service, sample_user):
    """DELETE /users/1 ahol 1 = current user → 400."""
    mock_user_service.delete.side_effect = ValueError("Saját magad nem törölheted.")
    r = client_superuser.delete("/api/users/1")
    assert r.status_code == 400


def test_resend_invite_success(client_superuser: TestClient, mock_user_service, sample_user):
    """POST /users/2/resend-invite inaktív usernek → 200."""
    pending_user = User(
        id=2,
        email="pending@example.com",
        password_hash="",
        is_active=False,
        role="user",
        created_at=datetime.now(timezone.utc),
        name=None,
    )
    mock_user_service.get_by_id.side_effect = lambda uid: pending_user if uid == 2 else (sample_user if uid == 1 else None)
    r = client_superuser.post("/api/users/2/resend-invite")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "pending@example.com"
    assert data.get("pending_registration") is True


def test_resend_invite_active_user_returns_400(client_superuser: TestClient, mock_user_service):
    """POST /users/1/resend-invite aktív usernek → 400."""
    mock_user_service.resend_invite.side_effect = ValueError(
        "A felhasználó már aktív. Csak inaktív (zárolt vagy megerősítésre váró) usereknek küldhető link."
    )
    r = client_superuser.post("/api/users/1/resend-invite")
    assert r.status_code == 400


def test_resend_invite_not_found_returns_400(client_superuser: TestClient, mock_user_service):
    """POST /users/999/resend-invite ha nincs user → 400 (ValueError User not found)."""
    mock_user_service.resend_invite.side_effect = ValueError("User not found")
    r = client_superuser.post("/api/users/999/resend-invite")
    assert r.status_code == 400
