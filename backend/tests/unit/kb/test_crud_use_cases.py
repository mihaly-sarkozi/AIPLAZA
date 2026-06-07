from __future__ import annotations

import pytest

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase
from apps.kb.kb_crud.dto.CreateKnowledgeBaseRequest import CreateKnowledgeBaseRequest
from apps.kb.kb_crud.dto.UpdateKnowledgeBaseRequest import UpdateKnowledgeBaseRequest
from apps.kb.kb_crud.errors.CrudNotFoundError import CrudNotFoundError
from apps.kb.kb_crud.errors.CrudValidationError import CrudValidationError
from apps.kb.kb_crud.service.ArchiveKnowledgeBaseService import ArchiveKnowledgeBaseService
from apps.kb.kb_crud.service.CreateKnowledgeBaseService import CreateKnowledgeBaseService
from apps.kb.kb_crud.service.GetKnowledgeBaseService import GetKnowledgeBaseService
from apps.kb.kb_crud.service.ListKnowledgeBasesService import ListKnowledgeBasesService
from apps.kb.kb_crud.service.UpdateKnowledgeBaseService import UpdateKnowledgeBaseService


class FakeKnowledgeBaseRepository:
    def __init__(self) -> None:
        self._items: dict[str, KnowledgeBase] = {}

    async def create(self, *, name: str, description: str | None, actor_user_id: int) -> KnowledgeBase:
        _ = actor_user_id
        if any(item.name == name for item in self._items.values()):
            raise CrudValidationError(CrudErrorCode.KB_NAME_EXISTS)
        kb = KnowledgeBase(id="kb_test_1", name=name, description=description, status="active")
        self._items[kb.id] = kb
        return kb

    async def list_all(self) -> list[KnowledgeBase]:
        return list(self._items.values())

    async def get_by_id(self, kb_id: str) -> KnowledgeBase:
        kb = self._items.get(kb_id)
        if kb is None:
            raise CrudNotFoundError(CrudErrorCode.KB_NOT_FOUND)
        return kb

    async def update(
        self,
        kb_id: str,
        *,
        name: str,
        description: str | None,
        actor_user_id: int,
    ) -> KnowledgeBase:
        _ = actor_user_id
        kb = await self.get_by_id(kb_id)
        updated = KnowledgeBase(id=kb.id, name=name, description=description, status=kb.status)
        self._items[kb_id] = updated
        return updated

    async def archive(self, kb_id: str) -> None:
        await self.get_by_id(kb_id)
        del self._items[kb_id]


@pytest.mark.asyncio
async def test_create_and_list_knowledge_base_services() -> None:
    repository = FakeKnowledgeBaseRepository()
    created = await CreateKnowledgeBaseService(repository).execute(
        CreateKnowledgeBaseRequest(name="Docs", description="Team docs"),
        actor_user_id=1,
    )
    listed = await ListKnowledgeBasesService(repository).execute()

    assert created.id == "kb_test_1"
    assert created.status == "active"
    assert len(listed) == 1
    assert listed[0].name == "Docs"


@pytest.mark.asyncio
async def test_get_update_and_archive_knowledge_base_services() -> None:
    repository = FakeKnowledgeBaseRepository()
    created = await CreateKnowledgeBaseService(repository).execute(
        CreateKnowledgeBaseRequest(name="Docs"),
        actor_user_id=1,
    )
    updated = await UpdateKnowledgeBaseService(repository).execute(
        created.id,
        UpdateKnowledgeBaseRequest(name="Docs v2", description="Updated"),
        actor_user_id=1,
    )
    fetched = await GetKnowledgeBaseService(repository).execute(created.id)
    await ArchiveKnowledgeBaseService(repository).execute(created.id)

    assert updated.name == "Docs v2"
    assert fetched.description == "Updated"
    with pytest.raises(CrudNotFoundError):
        await GetKnowledgeBaseService(repository).execute(created.id)
