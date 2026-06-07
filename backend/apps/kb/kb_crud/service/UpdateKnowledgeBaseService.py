from __future__ import annotations

from apps.kb.kb_crud.dto.KnowledgeBaseResponse import KnowledgeBaseResponse
from apps.kb.kb_crud.dto.UpdateKnowledgeBaseRequest import UpdateKnowledgeBaseRequest
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from apps.kb.kb_crud.service.KnowledgeBaseResponseMapper import to_response


class UpdateKnowledgeBaseService:
    def __init__(self, repository: KnowledgeBaseRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        kb_id: str,
        request: UpdateKnowledgeBaseRequest,
        *,
        actor_user_id: int,
    ) -> KnowledgeBaseResponse:
        kb = await self._repository.update(
            kb_id,
            name=request.name,
            description=request.description,
            actor_user_id=actor_user_id,
        )
        return to_response(kb)


__all__ = ["UpdateKnowledgeBaseService"]
