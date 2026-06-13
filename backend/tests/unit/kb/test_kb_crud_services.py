"""kb_crud use-case service unit tesztek (in-memory fake repository-kkal)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase
from apps.kb.kb_crud.dto.CreateKnowledgeBaseRequest import CreateKnowledgeBaseRequest
from apps.kb.kb_crud.dto.KbPermissionEntry import KbPermissionEntry
from apps.kb.kb_crud.errors.CrudLimitError import CrudLimitError
from apps.kb.kb_crud.errors.CrudPermissionError import CrudPermissionError
from apps.kb.kb_crud.errors.CrudValidationError import CrudValidationError
from apps.kb.kb_crud.service.CreateKnowledgeBaseService import CreateKnowledgeBaseService
from apps.kb.kb_crud.service.DeleteKnowledgeBaseService import DeleteKnowledgeBaseService
from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy
from apps.kb.kb_crud.service.KbCrudAuditLogger import KbCrudAuditLogger
from apps.kb.kb_crud.service.ListKnowledgeBasesService import ListKnowledgeBasesService
from apps.kb.kb_crud.service.SetKnowledgeBasePermissionsService import SetKnowledgeBasePermissionsService
from core.modules.users.domain.dto import User

pytestmark = pytest.mark.unit


def _run(coro):
    return asyncio.run(coro)


def _user(role: str = "owner", user_id: int = 1) -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@example.com",
        password_hash="",
        is_active=True,
        role=role,
        created_at=datetime.now(timezone.utc),
    )


def _kb(
    *,
    kb_id: int = 1,
    uuid: str = "kb-uuid-1",
    name: str = "Teszt KB",
    deleted_at: datetime | None = None,
    deleted_training_char_count: int = 0,
) -> KnowledgeBase:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return KnowledgeBase(
        id=kb_id,
        uuid=uuid,
        name=name,
        description=None,
        qdrant_collection_name=f"kb_{uuid}",
        personal_data_mode="no_personal_data",
        personal_data_sensitivity="medium",
        pii_depersonalization_enabled=True,
        public_enabled=False,
        created_at=now,
        updated_at=now,
        deleted_at=deleted_at,
        deleted_display_name=name if deleted_at else None,
        deleted_training_char_count=deleted_training_char_count,
    )


class FakeKbRepository:
    def __init__(self, items: list[KnowledgeBase] | None = None) -> None:
        self.items = list(items or [])
        self.soft_deleted: list[tuple[str, int]] = []

    async def create(self, *, name, description, pii_depersonalization_enabled, actor_user_id):
        kb = _kb(kb_id=len(self.items) + 1, uuid=f"kb-uuid-{len(self.items) + 1}", name=name)
        self.items.append(kb)
        return kb

    async def list_all(self, *, include_deleted: bool = False):
        if include_deleted:
            return list(self.items)
        return [kb for kb in self.items if not kb.is_deleted]

    async def get_by_uuid(self, kb_uuid):
        return next((kb for kb in self.items if kb.uuid == kb_uuid and not kb.is_deleted), None)

    async def get_by_name(self, name):
        return next((kb for kb in self.items if kb.name == name and not kb.is_deleted), None)

    async def update(self, kb_uuid, **kwargs):
        return await self.get_by_uuid(kb_uuid)

    async def soft_delete(self, kb_uuid, *, training_char_count: int = 0):
        self.soft_deleted.append((kb_uuid, training_char_count))


class FakePermissionRepository:
    def __init__(self, permissions: dict[str, list[tuple[int, str]]] | None = None) -> None:
        self.permissions = dict(permissions or {})

    async def list_permissions(self, kb_uuid):
        return list(self.permissions.get(kb_uuid, []))

    async def list_permissions_batch(self, kb_uuids):
        return {kb_uuid: list(self.permissions.get(kb_uuid, [])) for kb_uuid in kb_uuids}

    async def set_permissions(self, kb_uuid, permissions, *, actor_user_id):
        self.permissions[kb_uuid] = [
            (user_id, permission) for user_id, permission in permissions if permission in {"use", "train"}
        ]

    async def get_kb_ids_with_permission(self, user_id, permission):
        allowed = {"train"} if permission == "train" else {"use", "train"}
        result = []
        for kb_uuid, pairs in self.permissions.items():
            for uid, perm in pairs:
                if uid == user_id and perm in allowed:
                    result.append(self._kb_id_for(kb_uuid))
        return result

    def _kb_id_for(self, kb_uuid: str) -> int:
        return int(kb_uuid.rsplit("-", 1)[-1])


class FakeUsageLimit:
    def __init__(self, allowed: bool = True, reason: str | None = None) -> None:
        self._allowed = allowed
        self._reason = reason

    def can_create_kb(self, tenant: Any):
        return self._allowed, self._reason


class FakeTrainingSummary:
    def __init__(self, has_training: bool = False, char_count: int = 0) -> None:
        self._has_training = has_training
        self._char_count = char_count

    def has_training(self, kb_uuid: str) -> bool:
        return self._has_training

    def training_char_count(self, kb_uuid: str) -> int:
        return self._char_count


class FakeStorageMetrics:
    def __init__(self, metrics: dict[str, int] | None = None) -> None:
        self._metrics = metrics or {}

    def metrics_for(self, kb: KnowledgeBase) -> dict[str, int]:
        return dict(self._metrics)


class FakeContentCleanup:
    def __init__(self) -> None:
        self.cleared: list[str] = []

    def clear_contents(self, kb_uuid: str, *, confirm_name: str | None = None) -> dict[str, int]:
        self.cleared.append(kb_uuid)
        return {}


def _create_service(repo=None, perm_repo=None, usage=None) -> CreateKnowledgeBaseService:
    return CreateKnowledgeBaseService(
        repository=repo or FakeKbRepository(),
        permission_repository=perm_repo if perm_repo is not None else FakePermissionRepository(),
        usage_limit=usage or FakeUsageLimit(),
        audit=KbCrudAuditLogger(None),
    )


class TestCreateKnowledgeBaseService:
    def test_non_owner_cannot_create(self):
        service = _create_service()
        with pytest.raises(CrudPermissionError):
            _run(service.execute(CreateKnowledgeBaseRequest(name="KB"), actor=_user("admin"), tenant=None))

    def test_usage_limit_blocks_creation(self):
        service = _create_service(usage=FakeUsageLimit(allowed=False, reason="limit elérve"))
        with pytest.raises(CrudLimitError) as excinfo:
            _run(service.execute(CreateKnowledgeBaseRequest(name="KB"), actor=_user("owner"), tenant=None))
        assert excinfo.value.reason == "limit elérve"

    def test_duplicate_name_rejected(self):
        repo = FakeKbRepository([_kb(name="KB")])
        service = _create_service(repo=repo)
        with pytest.raises(CrudValidationError) as excinfo:
            _run(service.execute(CreateKnowledgeBaseRequest(name="KB"), actor=_user("owner"), tenant=None))
        assert excinfo.value.code == CrudErrorCode.KB_NAME_EXISTS.value

    def test_creator_gets_train_permission(self):
        perm_repo = FakePermissionRepository()
        service = _create_service(perm_repo=perm_repo)
        response = _run(
            service.execute(
                CreateKnowledgeBaseRequest(
                    name="Új KB",
                    permissions=[KbPermissionEntry(user_id=7, permission="use")],
                ),
                actor=_user("owner", user_id=1),
                tenant=None,
            )
        )
        assert response.name == "Új KB"
        stored = perm_repo.permissions[response.uuid]
        assert (7, "use") in stored
        assert (1, "train") in stored


class TestDeleteKnowledgeBaseService:
    def _service(self, repo=None, cleanup=None, summary=None):
        repo = repo or FakeKbRepository([_kb(uuid="kb-uuid-1", name="KB")])
        return DeleteKnowledgeBaseService(
            repository=repo,
            access_policy=KbAccessPolicy(repo, FakePermissionRepository()),
            content_cleanup=cleanup or FakeContentCleanup(),
            training_summary=summary or FakeTrainingSummary(char_count=123),
            audit=KbCrudAuditLogger(None),
        )

    def test_delete_blocked_for_non_owner(self):
        service = self._service()
        with pytest.raises(CrudPermissionError) as excinfo:
            _run(service.execute("kb-uuid-1", confirm_name="KB", actor=_user("admin")))
        assert excinfo.value.code == CrudErrorCode.KB_DELETE_NOT_ALLOWED.value

    def test_delete_allowed_for_owner(self):
        service = self._service()
        _run(service.execute("kb-uuid-1", confirm_name="KB", actor=_user("owner")))
        assert service._repository.soft_deleted == [("kb-uuid-1", 123)]

    def test_confirm_name_mismatch(self):
        service = self._service()
        with pytest.raises(CrudValidationError) as excinfo:
            _run(service.execute("kb-uuid-1", confirm_name="Rossz", actor=_user("owner")))
        assert excinfo.value.code == CrudErrorCode.KB_CONFIRM_NAME_MISMATCH.value

    def test_delete_clears_contents_and_soft_deletes_with_char_count(self):
        repo = FakeKbRepository([_kb(uuid="kb-uuid-1", name="KB")])
        cleanup = FakeContentCleanup()
        service = self._service(repo=repo, cleanup=cleanup, summary=FakeTrainingSummary(char_count=4567))
        _run(service.execute("kb-uuid-1", confirm_name="KB", actor=_user("owner")))
        assert cleanup.cleared == ["kb-uuid-1"]
        assert repo.soft_deleted == [("kb-uuid-1", 4567)]


class TestSetKnowledgeBasePermissionsService:
    def _service(self, repo, perm_repo):
        class _Users:
            def list_users(self):
                return []

        return SetKnowledgeBasePermissionsService(
            repository=repo,
            permission_repository=perm_repo,
            user_directory=_Users(),
            access_policy=KbAccessPolicy(repo, perm_repo),
            audit=KbCrudAuditLogger(None),
        )

    def test_self_permission_cannot_be_revoked(self):
        repo = FakeKbRepository([_kb(kb_id=1, uuid="kb-uuid-1", name="KB")])
        perm_repo = FakePermissionRepository({"kb-uuid-1": [(1, "train"), (7, "use")]})
        service = self._service(repo, perm_repo)
        _run(
            service.execute(
                "kb-uuid-1",
                [
                    KbPermissionEntry(user_id=1, permission="none"),
                    KbPermissionEntry(user_id=7, permission="train"),
                ],
                actor=_user("owner", user_id=1),
            )
        )
        stored = perm_repo.permissions["kb-uuid-1"]
        assert (1, "train") in stored
        assert (7, "train") in stored

    def test_user_without_train_permission_rejected(self):
        repo = FakeKbRepository([_kb(kb_id=1, uuid="kb-uuid-1", name="KB")])
        perm_repo = FakePermissionRepository({"kb-uuid-1": [(7, "use")]})
        service = self._service(repo, perm_repo)
        with pytest.raises(CrudPermissionError):
            _run(
                service.execute(
                    "kb-uuid-1",
                    [KbPermissionEntry(user_id=7, permission="train")],
                    actor=_user("user", user_id=7),
                )
            )


class TestListKnowledgeBasesService:
    def _service(self, repo, perm_repo, metrics=None):
        return ListKnowledgeBasesService(
            repository=repo,
            access_policy=KbAccessPolicy(repo, perm_repo),
            training_summary=FakeTrainingSummary(has_training=True),
            storage_metrics=metrics or FakeStorageMetrics(),
        )

    def test_owner_sees_deleted_only_with_training_chars(self):
        deleted_with_chars = _kb(
            kb_id=2,
            uuid="kb-uuid-2",
            name="Törölt sok karakterrel",
            deleted_at=datetime.now(timezone.utc).replace(tzinfo=None),
            deleted_training_char_count=999,
        )
        deleted_empty = _kb(
            kb_id=3,
            uuid="kb-uuid-3",
            name="Törölt üres",
            deleted_at=datetime.now(timezone.utc).replace(tzinfo=None),
            deleted_training_char_count=0,
        )
        repo = FakeKbRepository([_kb(kb_id=1, uuid="kb-uuid-1"), deleted_with_chars, deleted_empty])
        rows = _run(self._service(repo, FakePermissionRepository()).execute(current_user=_user("owner")))
        uuids = [row.uuid for row in rows]
        assert uuids == ["kb-uuid-1", "kb-uuid-2"]
        active_row = rows[0]
        assert active_row.can_train is True
        assert active_row.has_training is True
        deleted_row = rows[1]
        assert deleted_row.status == "deleted"
        assert deleted_row.can_train is False

    def test_plain_user_sees_only_permitted(self):
        repo = FakeKbRepository([_kb(kb_id=1, uuid="kb-uuid-1"), _kb(kb_id=2, uuid="kb-uuid-2", name="Másik")])
        perm_repo = FakePermissionRepository({"kb-uuid-2": [(5, "use")]})
        rows = _run(self._service(repo, perm_repo).execute(current_user=_user("user", user_id=5)))
        assert [row.uuid for row in rows] == ["kb-uuid-2"]
        assert rows[0].can_train is False
