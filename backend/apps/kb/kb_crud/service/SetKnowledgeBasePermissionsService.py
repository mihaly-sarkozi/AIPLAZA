from __future__ import annotations

# backend/apps/kb/kb_crud/service/SetKnowledgeBasePermissionsService.py
# Feladat: Tudástár jogosultságok beállítása (saját train jog megőrzésével, audittal).
# Sárközi Mihály - 2026.06.11

from typing import Any

from apps.kb.kb_crud.domain.KbPermissionLevel import KbPermissionLevel
from apps.kb.kb_crud.dto.KbPermissionEntry import KbPermissionEntry
from apps.kb.kb_crud.errors.CrudPermissionError import CrudPermissionError
from apps.kb.kb_crud.ports.KnowledgeBasePermissionRepository import KnowledgeBasePermissionRepository
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from apps.kb.kb_crud.ports.UserDirectoryInterface import UserDirectoryInterface
from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy
from apps.kb.kb_crud.service.KbCrudAuditLogger import KbCrudAuditLogger


class SetKnowledgeBasePermissionsService:
    def __init__(
        self,
        repository: KnowledgeBaseRepository,
        permission_repository: KnowledgeBasePermissionRepository,
        user_directory: UserDirectoryInterface,
        access_policy: KbAccessPolicy,
        audit: KbCrudAuditLogger,
    ) -> None:
        self._repository = repository
        self._permission_repository = permission_repository
        self._user_directory = user_directory
        self._access_policy = access_policy
        self._audit = audit

    async def execute(
        self,
        kb_uuid: str,
        entries: list[KbPermissionEntry],
        *,
        actor: Any,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if not await self._access_policy.user_can_train(kb_uuid, actor):
            raise CrudPermissionError()

        actor_user_id = int(actor.id)
        existing = await self._permission_repository.list_permissions(kb_uuid)
        new_permissions = self._merge_with_self_permission(entries, existing, actor_user_id)

        await self._permission_repository.set_permissions(
            kb_uuid,
            new_permissions,
            actor_user_id=actor_user_id,
        )

        kb = await self._repository.get_by_uuid(kb_uuid)
        users_by_id = {
            getattr(user, "id", None): user for user in self._user_directory.list_users()
        }
        self._audit.permission_changes(
            kb_uuid=kb_uuid,
            kb_name=kb.name if kb else None,
            old_permissions=existing,
            new_permissions=new_permissions,
            actor_user_id=actor_user_id,
            users_by_id=users_by_id,
            ip=ip,
            user_agent=user_agent,
        )

    @staticmethod
    def _merge_with_self_permission(
        entries: list[KbPermissionEntry],
        existing: list[tuple[int, str]],
        actor_user_id: int,
    ) -> list[tuple[int, str]]:
        """A hívó saját jogát nem lehet elvenni: az eddigi (vagy train) jogát megtartja."""
        none_value = KbPermissionLevel.NONE.value
        merged = [
            (entry.user_id, entry.permission.value)
            for entry in entries
            if entry.user_id != actor_user_id and entry.permission.value != none_value
        ]
        existing_self = next(
            (permission for user_id, permission in existing if user_id == actor_user_id),
            KbPermissionLevel.TRAIN.value,
        )
        merged.append((actor_user_id, existing_self or KbPermissionLevel.TRAIN.value))
        return merged


__all__ = ["SetKnowledgeBasePermissionsService"]
