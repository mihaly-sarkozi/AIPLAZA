from __future__ import annotations

from apps.kb.kb_crud.dto.KnowledgeBaseResponse import KnowledgeBaseResponse
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from apps.kb.kb_crud.service.KnowledgeBaseResponseMapper import to_response


class GetKnowledgeBaseService:
    def __init__(self, repository: KnowledgeBaseRepository) -> None:
        self._repository = repository

    async def execute(self, kb_id: str) -> KnowledgeBaseResponse:
        kb = await self._repository.get_by_id(kb_id)
        return to_response(kb)


__all__ = ["GetKnowledgeBaseService"]
