# tests/integration/test_knowledge.py
"""Knowledge base API tesztek: GET/POST /kb (admin), 401/403/success."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from apps.users.domain.user import User  # lightweight dataclass

pytestmark = pytest.mark.integration


class _KBOutLike:
    """KBOut-szerű objektum (response_model serializáláshoz valódi mezők kellenek)."""
    def __init__(self, uuid: str = "kb-123", name: str = "Test KB", description: str = "Desc"):
        now = datetime.now(timezone.utc)
        self.uuid = uuid
        self.name = name
        self.description = description
        self.qdrant_collection_name = "kb_123"
        self.created_at = now
        self.updated_at = now


@pytest.fixture
def mock_kb_service():
    """Knowledge base service mock: list_all, create, update, delete."""
    svc = MagicMock()
    svc.list_all.return_value = []
    svc.create.return_value = _KBOutLike()
    return svc


@pytest.fixture
def client_kb(app, client, sample_user, mock_kb_service):
    """Client + admin user (owner) + KB service mock."""
    from apps.core.di import get_kb_service
    from apps.core.security.auth_dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: sample_user
    app.dependency_overrides[get_kb_service] = lambda: mock_kb_service
    yield client
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_kb_service, None)


@pytest.fixture
def sample_user_role_user():
    """User role=user (nem admin) – GET /kb → 403."""
    return User(
        id=2,
        email="user@example.com",
        password_hash="",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )


def test_get_kb_without_auth_returns_401(client: TestClient):
    """GET /kb auth nélkül → 401."""
    r = client.get("/api/kb")
    assert r.status_code == 401


@pytest.mark.smoke_only
def test_get_kb_user_returns_200_filtered_list(client, sample_user_role_user, app):
    """GET /kb user szerepkörrel → 200, lista (csak use/train jogosult KB-k; mock üres repo → üres lista)."""
    from apps.core.security.auth_dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: sample_user_role_user
    try:
        r = client.get("/api/kb")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list), "Response must be a list"
        for item in data:
            assert isinstance(item, dict), "Each item must be a dict"
            assert "uuid" in item or "name" in item, "Each KB item must have uuid or name"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_get_kb_success_returns_list(client_kb: TestClient, mock_kb_service):
    """GET /kb admin/owner-rel → 200, lista (mock üres lista)."""
    r = client_kb.get("/api/kb")
    assert r.status_code == 200
    assert r.json() == []
    mock_kb_service.list_all.assert_called_once()


def test_post_kb_without_auth_returns_401(client: TestClient):
    """POST /kb auth nélkül → 401."""
    r = client.post("/api/kb", json={"name": "My KB", "description": "Desc"})
    assert r.status_code == 401


def test_post_kb_success_returns_created(client_kb: TestClient, mock_kb_service):
    """POST /kb admin/owner-rel érvényes body → 200, KB adatok."""
    r = client_kb.post("/api/kb", json={"name": "My KB", "description": "Desc"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("name") == "Test KB"
    assert data.get("uuid") == "kb-123"
    mock_kb_service.create.assert_called_once()
