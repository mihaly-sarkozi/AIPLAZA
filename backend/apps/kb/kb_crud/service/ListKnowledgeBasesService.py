from __future__ import annotations

from apps.kb.kb_crud.dto.KnowledgeBaseResponse import KnowledgeBaseResponse
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from apps.kb.kb_crud.service.KnowledgeBaseResponseMapper import to_response


class ListKnowledgeBasesService:
    def __init__(self, repository: KnowledgeBaseRepository) -> None:
        self._repository = repository

    async def execute(self) -> list[KnowledgeBaseResponse]:
        items = await self._repository.list_all()
        return [to_response(item) for item in items]


__all__ = ["ListKnowledgeBasesService"]
