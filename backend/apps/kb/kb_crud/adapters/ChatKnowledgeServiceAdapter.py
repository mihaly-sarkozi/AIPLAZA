from __future__ import annotations

from typing import Any

from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy


class ChatKnowledgeServiceAdapter:
    """Minimális chat/kb_search kompatibilitási adapter a legacy KNOWLEDGE_SERVICE kulcshoz."""

    def __init__(
        self,
        *,
        access_policy: KbAccessPolicy,
        repository: KnowledgeBaseRepository,
    ) -> None:
        self._access_policy = access_policy
        self._repository = repository

    async def user_can_use(self, kb_uuid: str, user_id: int | None = None, user: Any | None = None) -> bool:
        subject = user if user is not None else self._subject_from_user_id(user_id)
        if subject is None:
            return False
        return await self._access_policy.user_can_use(kb_uuid, subject)

    async def list_all(self, *, current_user_id: int | None = None, current_user: Any | None = None):
        subject = current_user if current_user is not None else self._subject_from_user_id(current_user_id)
        if subject is None:
            return []
        if self._access_policy.is_kb_manager(subject):
            return await self._repository.list_all(
                include_deleted=self._access_policy.is_owner(subject)
            )
        all_active = await self._repository.list_all()
        allowed_ids = await self._access_policy.usable_kb_ids(subject)
        return [kb for kb in all_active if kb.id is not None and kb.id in allowed_ids]

    @staticmethod
    def _subject_from_user_id(user_id: int | None) -> Any | None:
        if user_id is None:
            return None
        return type("ChatUser", (), {"id": user_id, "role": None, "is_active": True})()


__all__ = ["ChatKnowledgeServiceAdapter"]
