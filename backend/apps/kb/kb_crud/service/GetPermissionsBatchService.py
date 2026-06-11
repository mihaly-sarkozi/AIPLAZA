from __future__ import annotations

# backend/apps/kb/kb_crud/service/GetPermissionsBatchService.py
# Feladat: Több tudástár jogosultságainak lekérése egy kérésben (train jog ellenőrzéssel).
# Sárközi Mihály - 2026.06.11

from typing import Any

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.dto.KbPermissionResponse import KbPermissionResponse
from apps.kb.kb_crud.errors.CrudPermissionError import CrudPermissionError
from apps.kb.kb_crud.errors.CrudValidationError import CrudValidationError
from apps.kb.kb_crud.ports.KnowledgeBasePermissionRepository import KnowledgeBasePermissionRepository
from apps.kb.kb_crud.ports.UserDirectoryInterface import UserDirectoryInterface
from apps.kb.kb_crud.service.GetKnowledgeBasePermissionsService import build_permission_rows
from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy

MAX_BATCH_KB_IDS = 100


class GetPermissionsBatchService:
    def __init__(
        self,
        permission_repository: KnowledgeBasePermissionRepository,
        user_directory: UserDirectoryInterface,
        access_policy: KbAccessPolicy,
    ) -> None:
        self._permission_repository = permission_repository
        self._user_directory = user_directory
        self._access_policy = access_policy

    async def execute(
        self,
        kb_uuids: list[str],
        *,
        actor: Any,
    ) -> dict[str, list[KbPermissionResponse]]:
        unique_uuids = self._normalize_uuids(kb_uuids)
        if not unique_uuids:
            return {}
        if len(unique_uuids) > MAX_BATCH_KB_IDS:
            raise CrudValidationError(CrudErrorCode.TOO_MANY_KB_IDS)

        for kb_uuid in unique_uuids:
            if not await self._access_policy.user_can_train(kb_uuid, actor):
                raise CrudPermissionError()

        users = self._user_directory.list_users()
        permissions_by_kb = await self._permission_repository.list_permissions_batch(unique_uuids)
        return {
            kb_uuid: build_permission_rows(
                users,
                {user_id: permission for user_id, permission in (permissions_by_kb.get(kb_uuid) or [])},
            )
            for kb_uuid in unique_uuids
        }

    @staticmethod
    def _normalize_uuids(kb_uuids: list[str]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for raw in kb_uuids:
            kb_uuid = (raw or "").strip()
            if not kb_uuid or kb_uuid in seen:
                continue
            seen.add(kb_uuid)
            unique.append(kb_uuid)
        return unique


__all__ = ["GetPermissionsBatchService", "MAX_BATCH_KB_IDS"]
