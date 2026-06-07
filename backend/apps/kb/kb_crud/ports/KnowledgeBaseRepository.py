from __future__ import annotations

from typing import Protocol

from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase


class KnowledgeBaseRepository(Protocol):
    async def create(
        self,
        *,
        name: str,
        description: str | None,
        actor_user_id: int,
    ) -> KnowledgeBase: ...

    async def list_all(self) -> list[KnowledgeBase]: ...

    async def get_by_id(self, kb_id: str) -> KnowledgeBase: ...

    async def update(
        self,
        kb_id: str,
        *,
        name: str,
        description: str | None,
        actor_user_id: int,
    ) -> KnowledgeBase: ...

    async def archive(self, kb_id: str) -> None: ...


__all__ = ["KnowledgeBaseRepository"]
