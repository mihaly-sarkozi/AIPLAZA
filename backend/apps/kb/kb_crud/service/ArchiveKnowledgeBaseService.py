from __future__ import annotations

from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository


class ArchiveKnowledgeBaseService:
    def __init__(self, repository: KnowledgeBaseRepository) -> None:
        self._repository = repository

    async def execute(self, kb_id: str) -> None:
        await self._repository.archive(kb_id)


__all__ = ["ArchiveKnowledgeBaseService"]
