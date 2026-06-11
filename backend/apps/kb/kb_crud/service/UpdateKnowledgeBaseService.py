from __future__ import annotations

# backend/apps/kb/kb_crud/service/UpdateKnowledgeBaseService.py
# Feladat: Tudástár módosítás use-case (train jog, név-egyediség, beállítás audit).
# Sárközi Mihály - 2026.06.07

from typing import Any

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.dto.KnowledgeBaseResponse import KnowledgeBaseResponse
from apps.kb.kb_crud.dto.UpdateKnowledgeBaseRequest import UpdateKnowledgeBaseRequest
from apps.kb.kb_crud.errors.CrudNotFoundError import CrudNotFoundError
from apps.kb.kb_crud.errors.CrudPermissionError import CrudPermissionError
from apps.kb.kb_crud.errors.CrudValidationError import CrudValidationError
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy
from apps.kb.kb_crud.service.KbCrudAuditLogger import KbCrudAuditLogger
from apps.kb.kb_crud.service.KnowledgeBaseResponseMapper import to_response
from apps.kb.kb_crud.validation.ValidateKbName import ValidateKbName


class UpdateKnowledgeBaseService:
    def __init__(
        self,
        repository: KnowledgeBaseRepository,
        access_policy: KbAccessPolicy,
        audit: KbCrudAuditLogger,
    ) -> None:
        self._repository = repository
        self._access_policy = access_policy
        self._audit = audit

    async def execute(
        self,
        kb_uuid: str,
        request: UpdateKnowledgeBaseRequest,
        *,
        actor: Any,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> KnowledgeBaseResponse:
        if not await self._access_policy.user_can_train(kb_uuid, actor):
            raise CrudPermissionError()

        existing = await self._repository.get_by_uuid(kb_uuid)
        if existing is None:
            raise CrudNotFoundError(CrudErrorCode.KB_NOT_FOUND)

        name = ValidateKbName.execute(request.name)
        duplicate = await self._repository.get_by_name(name)
        if duplicate is not None and duplicate.uuid != kb_uuid:
            raise CrudValidationError(CrudErrorCode.KB_NAME_EXISTS)

        updated = await self._repository.update(
            kb_uuid,
            name=name,
            description=request.description,
            personal_data_mode=(
                request.personal_data_mode.value if request.personal_data_mode else None
            ),
            pii_depersonalization_enabled=request.pii_depersonalization_enabled,
            public_enabled=request.public_enabled,
            actor_user_id=int(actor.id),
        )
        self._audit.kb_setting_changes(
            existing,
            updated,
            actor_user_id=int(actor.id),
            ip=ip,
            user_agent=user_agent,
        )
        return to_response(updated, can_train=True)


__all__ = ["UpdateKnowledgeBaseService"]
