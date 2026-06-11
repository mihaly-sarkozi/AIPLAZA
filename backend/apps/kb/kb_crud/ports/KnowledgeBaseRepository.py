from __future__ import annotations

# backend/apps/kb/kb_crud/ports/KnowledgeBaseRepository.py
# Feladat: Tudástár repository szerződés (port) — a service réteg erre van típusozva.
# Sárközi Mihály - 2026.06.07

from typing import Protocol

from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase


class KnowledgeBaseRepository(Protocol):
    async def create(
        self,
        *,
        name: str,
        description: str | None,
        pii_depersonalization_enabled: bool,
        actor_user_id: int,
    ) -> KnowledgeBase: ...

    async def list_all(self, *, include_deleted: bool = False) -> list[KnowledgeBase]: ...

    async def get_by_uuid(self, kb_uuid: str) -> KnowledgeBase | None: ...

    async def get_by_name(self, name: str) -> KnowledgeBase | None: ...

    async def update(
        self,
        kb_uuid: str,
        *,
        name: str,
        description: str | None,
        personal_data_mode: str | None,
        pii_depersonalization_enabled: bool | None,
        public_enabled: bool | None,
        actor_user_id: int,
    ) -> KnowledgeBase: ...

    async def soft_delete(self, kb_uuid: str, *, training_char_count: int = 0) -> None: ...


__all__ = ["KnowledgeBaseRepository"]
