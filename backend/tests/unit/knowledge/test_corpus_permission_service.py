from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from apps.knowledge.domain.corpus import Corpus
from apps.knowledge.service.corpus_permission_service import CorpusPermissionService
from apps.knowledge.service.knowledge_permission_service import KnowledgePermissionService
from apps.knowledge.service import corpus_permission_service as permission_module

pytestmark = [pytest.mark.unit, pytest.mark.must_pass]


@dataclass(slots=True)
class _TenantRef:
    slug: str


@dataclass(slots=True)
class _UserRef:
    user_id: int
    tenant: _TenantRef
    role: str = "user"

    @property
    def id(self) -> int:
        return self.user_id


def tenant_factory(slug: str) -> _TenantRef:
    return _TenantRef(slug=slug)


def user_factory(*, tenant: _TenantRef, user_id: int, role: str = "user") -> _UserRef:
    return _UserRef(user_id=user_id, tenant=tenant, role=role)


def knowledge_base_factory(*, tenant: _TenantRef, kb_id: int, uuid: str) -> Corpus:
    return Corpus(
        id=kb_id,
        tenant=tenant.slug,
        uuid=uuid,
        name=f"KB-{uuid}",
        description=None,
        qdrant_collection_name=f"kb_{uuid}",
        created_at=None,
        updated_at=None,
    )


@pytest.fixture(autouse=True)
def _mock_has_permission(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(permission_module, "has_permission", lambda _user, _permission: False)


class _CorpusStore:
    def __init__(self) -> None:
        self.kbs = [
            Corpus(id=1, tenant="demo", uuid="kb-1", name="One", description=None, qdrant_collection_name="kb_1", created_at=None, updated_at=None),
            Corpus(id=2, tenant="demo", uuid="kb-2", name="Two", description=None, qdrant_collection_name="kb_2", created_at=None, updated_at=None),
        ]
        self.permissions = {"kb-1": [(11, "train")], "kb-2": [(12, "use")]}

    def list_all(self, include_deleted: bool = False):  # type: ignore[no-untyped-def]
        return list(self.kbs)

    def get_kb_ids_with_permission(self, user_id: int, permission: str):  # type: ignore[no-untyped-def]
        allowed = []
        for kb in self.kbs:
            for current_user_id, current_permission in self.permissions.get(kb.uuid, []):
                if current_user_id == user_id and current_permission == permission:
                    allowed.append(kb.id)
        return allowed

    def get_by_uuid(self, kb_uuid: str):  # type: ignore[no-untyped-def]
        return next((kb for kb in self.kbs if kb.uuid == kb_uuid), None)

    def list_permissions(self, kb_uuid: str):  # type: ignore[no-untyped-def]
        return list(self.permissions.get(kb_uuid, []))

    def list_permissions_batch(self, kb_uuids: list[str]):  # type: ignore[no-untyped-def]
        return {kb_uuid: self.list_permissions(kb_uuid) for kb_uuid in kb_uuids}

    def set_permissions(self, kb_uuid: str, permissions: list[tuple[int, str]], *, actor_user_id: int) -> None:
        self.permissions[kb_uuid] = list(permissions)


def _service(store: _CorpusStore) -> CorpusPermissionService:
    users = [
        SimpleNamespace(id=11, email="owner@example.test", name="Owner", role="owner"),
        SimpleNamespace(id=12, email="user@example.test", name="User", role="user"),
    ]
    return CorpusPermissionService(
        corpus_store=store,
        user_repo_list_all=lambda: users,
        corpus_mapper=lambda item: item,
        list_all_unfiltered=lambda: store.list_all(include_deleted=True),
    )


def _knowledge_permission_service(store: _CorpusStore) -> KnowledgePermissionService:
    users = [
        SimpleNamespace(id=11, email="owner@example.test", name="Owner", role="owner"),
        SimpleNamespace(id=12, email="user@example.test", name="User", role="user"),
    ]
    return KnowledgePermissionService(
        corpus_store=store,
        user_repo_list_all=lambda: users,
        corpus_mapper=lambda item: item,
        list_all_unfiltered=lambda: store.list_all(include_deleted=True),
    )


def test_user_can_train_uses_explicit_train_permission() -> None:
    store = _CorpusStore()
    service = _service(store)

    assert service.user_can_train("kb-1", 11, None) is True
    assert service.user_can_train("kb-2", 11, None) is False


def test_user_without_permission_cannot_see_other_tenant_kb_boundary() -> None:
    store = _CorpusStore()
    service = _service(store)

    visible = service.list_all(current_user_id=99, current_user=None)

    assert visible == []
    assert service.user_can_use("kb-1", 99, None) is False
    assert service.user_can_train("kb-1", 99, None) is False


def test_corpus_permission_boundary_separates_use_and_train() -> None:
    store = _CorpusStore()
    service = _service(store)

    assert service.user_can_use("kb-2", 12, None) is True
    assert service.user_can_train("kb-2", 12, None) is False


def test_set_permissions_preserves_current_user_permission() -> None:
    store = _CorpusStore()
    service = _service(store)

    service.set_permissions("kb-1", [(12, "use")], current_user_id=11)

    assert sorted(store.permissions["kb-1"]) == [(11, "train"), (12, "use")]


def test_tenant_a_user_cannot_see_tenant_b_knowledge_base_with_factories() -> None:
    tenant_a = tenant_factory("tenant-a")
    tenant_b = tenant_factory("tenant-b")
    user_a = user_factory(tenant=tenant_a, user_id=11)
    kb_a = knowledge_base_factory(tenant=tenant_a, kb_id=101, uuid="kb-a")
    kb_b = knowledge_base_factory(tenant=tenant_b, kb_id=202, uuid="kb-b")

    store = _CorpusStore()
    store.kbs = [kb_a, kb_b]
    store.permissions = {kb_a.uuid: [(user_a.id, "use")], kb_b.uuid: []}
    service = _service(store)

    visible = service.list_all(current_user_id=user_a.id, current_user=None)

    assert [item.uuid for item in visible] == ["kb-a"]
    assert all(item.tenant == tenant_a.slug for item in visible)


def test_admin_scope_can_access_train_and_use_permissions(monkeypatch: pytest.MonkeyPatch) -> None:
    admin_user = SimpleNamespace(id=77, role="admin")
    monkeypatch.setattr(
        permission_module,
        "has_permission",
        lambda user, permission: bool(user is admin_user and permission == "knowledge.write"),
    )
    store = _CorpusStore()
    service = _service(store)

    assert service.user_can_use("kb-1", admin_user.id, admin_user) is True
    assert service.user_can_train("kb-2", admin_user.id, admin_user) is True


def test_knowledge_permission_service_centralizes_metrics_policy() -> None:
    service = _knowledge_permission_service(_CorpusStore())

    assert service.can_view_knowledge_metrics(SimpleNamespace(id=1, role="owner")) is True
    assert service.can_view_knowledge_metrics(SimpleNamespace(id=2, role="admin")) is True
    assert service.can_view_knowledge_metrics(SimpleNamespace(id=3, role="user")) is False


def test_knowledge_permission_service_centralizes_train_policy() -> None:
    store = _CorpusStore()
    service = _knowledge_permission_service(store)

    assert service.can_train_knowledge_base(SimpleNamespace(id=11, role="user"), store.kbs[0]) is True
    assert service.can_train_knowledge_base(SimpleNamespace(id=12, role="user"), store.kbs[0]) is False
