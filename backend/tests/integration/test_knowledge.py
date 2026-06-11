"""Knowledge base API tesztek az új kb_crud végpontokon: GET/POST /kb, 401/szerepkör/siker."""
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from core.modules.users.domain.dto import User  # lightweight dataclass

pytestmark = pytest.mark.integration


def _kb_domain(uuid: str = "kb-123", name: str = "Test KB", description: str = "Desc"):
    from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return KnowledgeBase(
        id=1,
        uuid=uuid,
        name=name,
        description=description,
        qdrant_collection_name="kb_123",
        personal_data_mode="no_personal_data",
        personal_data_sensitivity="medium",
        pii_depersonalization_enabled=True,
        public_enabled=False,
        created_at=now,
        updated_at=now,
    )


class _AsyncRepoStub:
    """KnowledgeBaseRepository stub async metódusokkal."""

    def __init__(self, items=None):
        self.items = list(items or [])
        self.created = []

    async def list_all(self, *, include_deleted: bool = False):
        return list(self.items)

    async def get_by_uuid(self, kb_uuid):
        return next((kb for kb in self.items if kb.uuid == kb_uuid), None)

    async def get_by_name(self, name):
        return next((kb for kb in self.items if kb.name == name), None)

    async def create(self, *, name, description, pii_depersonalization_enabled, actor_user_id):
        kb = _kb_domain(name=name, description=description)
        self.created.append(kb)
        return kb


class _PermissionRepoStub:
    def __init__(self, train_kb_ids=None):
        self._train_kb_ids = list(train_kb_ids or [])
        self.saved = []

    async def list_permissions(self, kb_uuid):
        return []

    async def set_permissions(self, kb_uuid, permissions, *, actor_user_id):
        self.saved.append((kb_uuid, list(permissions)))

    async def get_kb_ids_with_permission(self, user_id, permission):
        return list(self._train_kb_ids)


class _TrainingSummaryStub:
    def __init__(self, has_training: bool = False):
        self._has_training = has_training
        self.calls = []

    def has_training(self, kb_uuid):
        self.calls.append(kb_uuid)
        return self._has_training

    def training_char_count(self, kb_uuid):
        return 0


class _StorageMetricsStub:
    def metrics_for(self, kb):
        return {}


@pytest.fixture
def sample_user_role_user():
    """User role=user (nem admin)."""
    return User(
        id=2,
        email="user@example.com",
        password_hash="",
        is_active=True,
        role="user",
        created_at=datetime.now(timezone.utc),
    )


def _build_list_service(repo, perm_repo, training_summary):
    from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy
    from apps.kb.kb_crud.service.ListKnowledgeBasesService import ListKnowledgeBasesService

    return ListKnowledgeBasesService(
        repository=repo,
        access_policy=KbAccessPolicy(repo, perm_repo),
        training_summary=training_summary,
        storage_metrics=_StorageMetricsStub(),
    )


def _build_create_service(repo, perm_repo):
    from apps.kb.kb_crud.service.CreateKnowledgeBaseService import CreateKnowledgeBaseService
    from apps.kb.kb_crud.service.KbCrudAuditLogger import KbCrudAuditLogger

    usage = MagicMock()
    usage.can_create_kb.return_value = (True, None)
    return CreateKnowledgeBaseService(
        repository=repo,
        permission_repository=perm_repo,
        usage_limit=usage,
        audit=KbCrudAuditLogger(None),
    )


@pytest.fixture
def kb_stubs():
    return {
        "repo": _AsyncRepoStub(),
        "perm_repo": _PermissionRepoStub(),
        "training_summary": _TrainingSummaryStub(),
    }


@pytest.fixture
def client_kb(app, client, sample_user, kb_stubs):
    """Client + owner user + kb_crud service stubok."""
    from apps.kb.kb_crud.bootstrap.dependencies import (
        get_create_knowledge_base_service,
        get_list_knowledge_bases_service,
    )
    from core.modules.auth.web.dependencies.auth_dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: sample_user
    app.dependency_overrides[get_list_knowledge_bases_service] = lambda: _build_list_service(
        kb_stubs["repo"], kb_stubs["perm_repo"], kb_stubs["training_summary"]
    )
    app.dependency_overrides[get_create_knowledge_base_service] = lambda: _build_create_service(
        kb_stubs["repo"], kb_stubs["perm_repo"]
    )
    yield client
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_list_knowledge_bases_service, None)
    app.dependency_overrides.pop(get_create_knowledge_base_service, None)


def test_get_kb_without_auth_returns_401(client: TestClient):
    """GET /kb auth nélkül → 401."""
    r = client.get("/api/kb")
    assert r.status_code == 401


@pytest.mark.smoke_only
def test_get_kb_user_returns_200_filtered_list(client, sample_user_role_user, app, kb_stubs):
    """GET /kb user szerepkörrel → 200, lista (csak use/train jogosult KB-k; üres repo → üres lista)."""
    from apps.kb.kb_crud.bootstrap.dependencies import get_list_knowledge_bases_service
    from core.modules.auth.web.dependencies.auth_dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: sample_user_role_user
    app.dependency_overrides[get_list_knowledge_bases_service] = lambda: _build_list_service(
        kb_stubs["repo"], kb_stubs["perm_repo"], kb_stubs["training_summary"]
    )
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
        app.dependency_overrides.pop(get_list_knowledge_bases_service, None)


def test_get_kb_success_returns_list(client_kb: TestClient):
    """GET /kb admin/owner-rel → 200, lista (üres stub → üres lista)."""
    r = client_kb.get("/api/kb")
    assert r.status_code == 200
    assert r.json() == []


def test_get_kb_list_marks_available_kb_ingest_entries(client_kb: TestClient, kb_stubs):
    kb_stubs["repo"].items = [_kb_domain(uuid="kb-trained", name="Trained KB")]
    kb_stubs["training_summary"]._has_training = True

    r = client_kb.get("/api/kb")

    assert r.status_code == 200
    data = r.json()
    assert data[0]["uuid"] == "kb-trained"
    assert data[0]["has_training"] is True
    assert kb_stubs["training_summary"].calls == ["kb-trained"]


def test_post_kb_without_auth_returns_401(client: TestClient):
    """POST /kb auth nélkül → 401."""
    r = client.post("/api/kb", json={"name": "My KB", "description": "Desc"})
    assert r.status_code == 401


def test_post_kb_success_returns_created(client_kb: TestClient, kb_stubs):
    """POST /kb owner-rel érvényes body → 200, KB adatok + létrehozói train jog."""
    r = client_kb.post("/api/kb", json={"name": "My KB", "description": "Desc"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("name") == "My KB"
    assert data.get("uuid") == "kb-123"
    assert len(kb_stubs["repo"].created) == 1
    assert kb_stubs["perm_repo"].saved, "A létrehozónak induló jogosultságot kell kapnia"
    saved_kb_uuid, saved_permissions = kb_stubs["perm_repo"].saved[0]
    assert saved_kb_uuid == "kb-123"
    assert (1, "train") in saved_permissions
