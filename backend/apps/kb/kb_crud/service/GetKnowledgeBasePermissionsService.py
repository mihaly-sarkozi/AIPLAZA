from __future__ import annotations

# backend/apps/kb/kb_crud/service/GetKnowledgeBasePermissionsService.py
# Feladat: Egy tudástár jogosultságainak listázása minden tenant felhasználóra.
# Sárközi Mihály - 2026.06.11

from typing import Any

from apps.kb.kb_crud.domain.KbPermissionLevel import KbPermissionLevel
from apps.kb.kb_crud.dto.KbPermissionResponse import KbPermissionResponse
from apps.kb.kb_crud.errors.CrudPermissionError import CrudPermissionError
from apps.kb.kb_crud.ports.KnowledgeBasePermissionRepository import KnowledgeBasePermissionRepository
from apps.kb.kb_crud.ports.UserDirectoryInterface import UserDirectoryInterface
from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy


def build_permission_rows(
    users: list[Any],
    permission_by_user: dict[int, str],
) -> list[KbPermissionResponse]:
    rows: list[KbPermissionResponse] = []
    for user in users:
        user_id = getattr(user, "id", None)
        if user_id is None:
            continue
        rows.append(
            KbPermissionResponse(
                user_id=int(user_id),
                email=getattr(user, "email", "") or "",
                name=getattr(user, "name", None),
                permission=permission_by_user.get(user_id, KbPermissionLevel.NONE.value),
                role=getattr(user, "role", "user") or "user",
            )
        )
    return rows


class GetKnowledgeBasePermissionsService:
    def __init__(
        self,
        permission_repository: KnowledgeBasePermissionRepository,
        user_directory: UserDirectoryInterface,
        access_policy: KbAccessPolicy,
    ) -> None:
        self._permission_repository = permission_repository
        self._user_directory = user_directory
        self._access_policy = access_policy

    async def execute(self, kb_uuid: str, *, actor: Any) -> list[KbPermissionResponse]:
        if not await self._access_policy.user_can_train(kb_uuid, actor):
            raise CrudPermissionError()
        permissions = await self._permission_repository.list_permissions(kb_uuid)
        permission_by_user = {user_id: permission for user_id, permission in permissions}
        return build_permission_rows(self._user_directory.list_users(), permission_by_user)


__all__ = ["GetKnowledgeBasePermissionsService", "build_permission_rows"]
