from __future__ import annotations

from apps.kb.kb_crud.dto.CreateKnowledgeBaseRequest import CreateKnowledgeBaseRequest
from apps.kb.kb_crud.dto.KnowledgeBaseResponse import KnowledgeBaseResponse
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from apps.kb.kb_crud.service.KnowledgeBaseResponseMapper import to_response


class CreateKnowledgeBaseService:
    def __init__(self, repository: KnowledgeBaseRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        request: CreateKnowledgeBaseRequest,
        *,
        actor_user_id: int,
    ) -> KnowledgeBaseResponse:
        kb = await self._repository.create(
            name=request.name,
            description=request.description,
            actor_user_id=actor_user_id,
        )
        return to_response(kb)


__all__ = ["CreateKnowledgeBaseService"]
