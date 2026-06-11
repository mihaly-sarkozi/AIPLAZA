from __future__ import annotations

# backend/apps/kb/kb_crud/service/KbAccessPolicy.py
# Feladat: Tudástár hozzáférési döntések egy helyen (ki láthat, ki taníthat).
# Sárközi Mihály - 2026.06.11

from typing import Any

from apps.kb.kb_crud.domain.KbPermissionLevel import KbPermissionLevel
from apps.kb.kb_crud.ports.KnowledgeBasePermissionRepository import KnowledgeBasePermissionRepository
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository

_MANAGER_ROLES = {"owner", "admin"}


class KbAccessPolicy:
    def __init__(
        self,
        repository: KnowledgeBaseRepository,
        permission_repository: KnowledgeBasePermissionRepository,
    ) -> None:
        self._repository = repository
        self._permission_repository = permission_repository

    @staticmethod
    def is_kb_manager(user: Any | None) -> bool:
        return str(getattr(user, "role", "") or "").strip().lower() in _MANAGER_ROLES

    @staticmethod
    def is_owner(user: Any | None) -> bool:
        return str(getattr(user, "role", "") or "").strip().lower() == "owner"

    async def user_can_train(self, kb_uuid: str, user: Any | None) -> bool:
        return await self._user_has_permission(kb_uuid, user, KbPermissionLevel.TRAIN.value)

    async def user_can_use(self, kb_uuid: str, user: Any | None) -> bool:
        return await self._user_has_permission(kb_uuid, user, KbPermissionLevel.USE.value)

    async def trainable_kb_ids(self, user: Any | None) -> set[int]:
        if self.is_kb_manager(user):
            items = await self._repository.list_all(include_deleted=True)
            return {item.id for item in items if item.id is not None}
        user_id = self._user_id(user)
        if user_id is None:
            return set()
        return set(
            await self._permission_repository.get_kb_ids_with_permission(
                user_id, KbPermissionLevel.TRAIN.value
            )
        )

    async def usable_kb_ids(self, user: Any | None) -> set[int]:
        user_id = self._user_id(user)
        if user_id is None:
            return set()
        return set(
            await self._permission_repository.get_kb_ids_with_permission(
                user_id, KbPermissionLevel.USE.value
            )
        )

    async def _user_has_permission(self, kb_uuid: str, user: Any | None, permission: str) -> bool:
        if self.is_kb_manager(user):
            return True
        user_id = self._user_id(user)
        if user_id is None:
            return False
        kb = await self._repository.get_by_uuid(kb_uuid)
        if kb is None or kb.id is None:
            return False
        allowed_ids = await self._permission_repository.get_kb_ids_with_permission(user_id, permission)
        return kb.id in allowed_ids

    @staticmethod
    def _user_id(user: Any | None) -> int | None:
        user_id = getattr(user, "id", None)
        if user_id is None:
            return None
        try:
            return int(user_id)
        except (TypeError, ValueError):
            return None


__all__ = ["KbAccessPolicy"]
