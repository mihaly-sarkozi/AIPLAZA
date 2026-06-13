from __future__ import annotations

# backend/apps/kb/kb_crud/service/DeleteKnowledgeBaseService.py
# Feladat: Tudástár törlés use-case (csak owner, név megerősítés, tartalom
# ürítés, soft delete a tanított karakterszám megőrzésével, audit).
# Sárközi Mihály - 2026.06.07

from typing import Any

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.kb_crud.errors.CrudNotFoundError import CrudNotFoundError
from apps.kb.kb_crud.errors.CrudPermissionError import CrudPermissionError
from apps.kb.kb_crud.errors.CrudValidationError import CrudValidationError
from apps.kb.kb_crud.ports.ContentCleanupInterface import ContentCleanupInterface
from apps.kb.kb_crud.ports.KnowledgeBaseRepository import KnowledgeBaseRepository
from apps.kb.kb_crud.ports.TrainingSummaryInterface import TrainingSummaryInterface
from apps.kb.kb_crud.service.KbAccessPolicy import KbAccessPolicy
from apps.kb.kb_crud.service.KbCrudAuditLogger import KbCrudAuditLogger


class DeleteKnowledgeBaseService:
    def __init__(
        self,
        repository: KnowledgeBaseRepository,
        access_policy: KbAccessPolicy,
        content_cleanup: ContentCleanupInterface,
        training_summary: TrainingSummaryInterface,
        audit: KbCrudAuditLogger,
    ) -> None:
        self._repository = repository
        self._access_policy = access_policy
        self._content_cleanup = content_cleanup
        self._training_summary = training_summary
        self._audit = audit

    async def execute(
        self,
        kb_uuid: str,
        *,
        confirm_name: str,
        actor: Any,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        if not self._access_policy.is_owner(actor):
            raise CrudPermissionError(CrudErrorCode.KB_DELETE_NOT_ALLOWED)
        if not await self._access_policy.user_can_train(kb_uuid, actor):
            raise CrudPermissionError()

        kb = await self._repository.get_by_uuid(kb_uuid)
        if kb is None:
            raise CrudNotFoundError(CrudErrorCode.KB_NOT_FOUND)
        if confirm_name and confirm_name != kb.name:
            raise CrudValidationError(CrudErrorCode.KB_CONFIRM_NAME_MISMATCH)

        training_char_count = self._training_summary.training_char_count(kb_uuid)
        self._content_cleanup.clear_contents(kb_uuid, confirm_name=confirm_name)
        await self._repository.soft_delete(kb_uuid, training_char_count=training_char_count)
        self._audit.kb_deleted(
            kb,
            actor_user_id=int(actor.id),
            training_char_count=training_char_count,
            ip=ip,
            user_agent=user_agent,
        )


__all__ = ["DeleteKnowledgeBaseService"]
