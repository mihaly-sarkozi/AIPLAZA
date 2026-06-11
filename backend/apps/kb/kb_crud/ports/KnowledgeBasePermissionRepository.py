from __future__ import annotations

# backend/apps/kb/kb_crud/ports/KnowledgeBasePermissionRepository.py
# Feladat: Tudástár jogosultság repository szerződés (port).
# Sárközi Mihály - 2026.06.11

from typing import Protocol

KbPermissionPair = tuple[int, str]


class KnowledgeBasePermissionRepository(Protocol):
    async def list_permissions(self, kb_uuid: str) -> list[KbPermissionPair]: ...

    async def list_permissions_batch(self, kb_uuids: list[str]) -> dict[str, list[KbPermissionPair]]: ...

    async def set_permissions(
        self,
        kb_uuid: str,
        permissions: list[KbPermissionPair],
        *,
        actor_user_id: int,
    ) -> None: ...

    async def get_kb_ids_with_permission(self, user_id: int, permission: str) -> list[int]: ...


__all__ = ["KbPermissionPair", "KnowledgeBasePermissionRepository"]
