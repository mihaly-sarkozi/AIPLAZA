from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from core.modules.users.domain.dto import User

pytestmark = [pytest.mark.integration, pytest.mark.must_pass]


def test_list_users_skips_incomplete_and_sets_pending_registration(client_superuser: TestClient, mock_user_service):
    pending = User(
        id=10,
        email="pending@example.com",
        password_hash="hash",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
        registration_completed_at=None,
        credentials_password_set=False,
    )
    completed_inactive = User(
        id=11,
        email="completed@example.com",
        password_hash="hash",
        is_active=False,
        role="user",
        created_at=datetime.now(timezone.utc),
        registration_completed_at=datetime.now(timezone.utc),
    )
    incomplete = User(
        id=None,
        email="broken@example.com",
        password_hash="hash",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )
    mock_user_service.list_all.return_value = [pending, completed_inactive, incomplete]

    response = client_superuser.get("/api/users")

    assert response.status_code == 200
    data = response.json()
    assert [item["email"] for item in data] == ["pending@example.com", "completed@example.com"]
    assert data[0]["pending_registration"] is True
    assert data[1]["pending_registration"] is False


def test_get_user_returns_500_for_incomplete_user_data(client_superuser: TestClient, mock_user_service):
    incomplete = User(
        id=55,
        email="incomplete@example.com",
        password_hash="hash",
        is_active=True,
        role="user",
        created_at=None,
    )
    mock_user_service.get_by_id.side_effect = lambda uid: incomplete if uid == 55 else None

    response = client_superuser.get("/api/users/55")

    assert response.status_code == 500
    assert response.json()["detail"] == "User data is incomplete"
