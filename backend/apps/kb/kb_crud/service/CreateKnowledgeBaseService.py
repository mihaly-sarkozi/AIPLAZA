from __future__ import annotations

# backend/apps/kb/kb_crud/service/CreateKnowledgeBaseService.py
# Feladat: Tudástár létrehozás use-case (owner szabály, limit, név-egyediség,
# induló jogosultságok, audit).
# Sárközi Mihály - 2026.06.07

from typing import Any

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.domain.KbPermissionLevel import KbPermissionLevel
from apps.kb.kb_crud.dto.CreateKnowledgeBaseRequest import CreateKnowledgeBaseRequest
from apps.kb.kb_crud.dto.KnowledgeBaseResponse import KnowledgeBaseResponse
from apps.kb.kb_crud.errors.CrudLimitError import CrudLimitError
from apps.kb.kb_crud.errors.CrudPermissionError import CrudPermissionError
from apps.kb.kb_crud.errors.CrudValidationError import CrudValidationError
from apps.kb.kb_crud.ports.KnowledgeBasePermissionRepository import KnowledgeBasePermissionRepository
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from apps.kb.kb_crud.ports.UsageLimitInterface import UsageLimitInterface
from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy
from apps.kb.kb_crud.service.KbCrudAuditLogger import KbCrudAuditLogger
from apps.kb.kb_crud.service.KnowledgeBaseResponseMapper import to_response
from apps.kb.kb_crud.validation.ValidateKbName import ValidateKbName


class CreateKnowledgeBaseService:
    def __init__(
        self,
        repository: KnowledgeBaseRepository,
        permission_repository: KnowledgeBasePermissionRepository,
        usage_limit: UsageLimitInterface,
        audit: KbCrudAuditLogger,
    ) -> None:
        self._repository = repository
        self._permission_repository = permission_repository
        self._usage_limit = usage_limit
        self._audit = audit

    async def execute(
        self,
        request: CreateKnowledgeBaseRequest,
        *,
        actor: Any,
        tenant: Any,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> KnowledgeBaseResponse:
        if not KbAccessPolicy.is_owner(actor):
            raise CrudPermissionError()

        allowed, reason = self._usage_limit.can_create_kb(tenant)
        if not allowed:
            raise CrudLimitError(reason)

        name = ValidateKbName.execute(request.name)
        if await self._repository.get_by_name(name) is not None:
            raise CrudValidationError(CrudErrorCode.KB_NAME_EXISTS)

        actor_user_id = int(actor.id)
        kb = await self._repository.create(
            name=name,
            description=request.description,
            pii_depersonalization_enabled=True,
            actor_user_id=actor_user_id,
        )

        permissions = self._initial_permissions(request, actor_user_id)
        await self._permission_repository.set_permissions(
            kb.uuid,
            permissions,
            actor_user_id=actor_user_id,
        )

        self._audit.kb_created(kb, actor_user_id=actor_user_id, ip=ip, user_agent=user_agent)
        self._audit.permission_changes(
            kb_uuid=kb.uuid,
            kb_name=kb.name,
            old_permissions=[],
            new_permissions=permissions,
            actor_user_id=actor_user_id,
            ip=ip,
            user_agent=user_agent,
        )
        return to_response(kb, can_train=True, has_training=False)

    @staticmethod
    def _initial_permissions(
        request: CreateKnowledgeBaseRequest,
        actor_user_id: int,
    ) -> list[tuple[int, str]]:
        none_value = KbPermissionLevel.NONE.value
        permissions = [
            (entry.user_id, entry.permission.value)
            for entry in (request.permissions or [])
            if entry.permission.value != none_value
        ]
        if not any(user_id == actor_user_id for user_id, _ in permissions):
            permissions.append((actor_user_id, KbPermissionLevel.TRAIN.value))
        return permissions


__all__ = ["CreateKnowledgeBaseService"]
