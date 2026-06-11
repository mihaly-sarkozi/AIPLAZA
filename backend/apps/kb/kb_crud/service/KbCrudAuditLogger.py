from __future__ import annotations

# backend/apps/kb/kb_crud/service/KbCrudAuditLogger.py
# Feladat: Tudástár CRUD audit események egységes naplózása (a legacy payload paritásával).
# Sárközi Mihály - 2026.06.11

import logging
from typing import Any

from apps.kb.kb_crud.domain.KbPermissionLevel import KbPermissionLevel
from apps.kb.kb_crud.domain.KnowledgeBase import KnowledgeBase
from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction

logger = logging.getLogger(__name__)


class KbCrudAuditLogger:
    def __init__(self, audit_service: Any | None) -> None:
        self._audit = audit_service

    def kb_created(
        self,
        kb: KnowledgeBase,
        *,
        actor_user_id: int | None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self._log(
            AuditLogAction.KNOWLEDGE_CREATED,
            user_id=actor_user_id,
            target_id=kb.uuid,
            details={
                "kb_uuid": kb.uuid,
                "kb_name": kb.name,
                "changed_by": actor_user_id,
                "pii_depersonalization_enabled": bool(kb.pii_depersonalization_enabled),
                "public_enabled": bool(kb.public_enabled),
            },
            ip=ip,
            user_agent=user_agent,
        )

    def kb_deleted(
        self,
        kb: KnowledgeBase,
        *,
        actor_user_id: int | None,
        training_char_count: int,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self._log(
            AuditLogAction.KNOWLEDGE_DELETED,
            user_id=actor_user_id,
            target_id=kb.uuid,
            details={
                "kb_uuid": kb.uuid,
                "kb_name": kb.name,
                "changed_by": actor_user_id,
                "training_char_count": training_char_count,
            },
            ip=ip,
            user_agent=user_agent,
        )

    def kb_setting_changes(
        self,
        old: KnowledgeBase,
        new: KnowledgeBase,
        *,
        actor_user_id: int | None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        fields = (
            ("public_enabled", old.public_enabled, new.public_enabled),
            ("pii_depersonalization_enabled", old.pii_depersonalization_enabled, new.pii_depersonalization_enabled),
        )
        for field, old_value, new_value in fields:
            if bool(old_value) == bool(new_value):
                continue
            self._log(
                AuditLogAction.KNOWLEDGE_SETTING_CHANGED,
                user_id=actor_user_id,
                target_id=new.uuid,
                details={
                    "kb_uuid": new.uuid,
                    "kb_name": new.name,
                    "field": field,
                    "old_value": bool(old_value),
                    "new_value": bool(new_value),
                    "changed_by": actor_user_id,
                },
                ip=ip,
                user_agent=user_agent,
            )

    def permission_changes(
        self,
        *,
        kb_uuid: str,
        kb_name: str | None,
        old_permissions: list[tuple[int, str]],
        new_permissions: list[tuple[int, str]],
        actor_user_id: int | None,
        users_by_id: dict[int | None, Any] | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        none_value = KbPermissionLevel.NONE.value
        old_by_user = {int(uid): perm or none_value for uid, perm in old_permissions}
        new_by_user = {int(uid): perm or none_value for uid, perm in new_permissions}
        users = users_by_id or {}
        for user_id in sorted(set(old_by_user) | set(new_by_user)):
            old_perm = old_by_user.get(user_id, none_value)
            new_perm = new_by_user.get(user_id, none_value)
            if old_perm == new_perm:
                continue
            user = users.get(user_id)
            details: dict[str, Any] = {
                "kb_uuid": kb_uuid,
                "kb_name": kb_name,
                "old_permission": old_perm,
                "new_permission": new_perm,
                "changed_by": actor_user_id,
            }
            if user is not None:
                details["email"] = getattr(user, "email", None)
                details["name"] = getattr(user, "name", None)
            self._log(
                AuditLogAction.KNOWLEDGE_PERMISSION_CHANGED,
                user_id=user_id,
                target_id=kb_uuid,
                details=details,
                ip=ip,
                user_agent=user_agent,
            )

    def _log(
        self,
        action: AuditLogAction,
        *,
        user_id: int | None,
        target_id: str,
        details: dict[str, Any],
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        if self._audit is None:
            return
        try:
            self._audit.log(
                action,
                user_id=user_id,
                target_type="knowledge_base",
                target_id=target_id,
                details=details,
                ip=ip,
                user_agent=user_agent,
            )
        except Exception:
            logger.warning("kb_crud.audit_log_failed", exc_info=True)


__all__ = ["KbCrudAuditLogger"]
