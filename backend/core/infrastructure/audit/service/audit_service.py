# backend/core/infrastructure/audit/service/audit_service.py
# Feladat: Az audit események alkalmazási service rétege. Default actor/outcome/target értékeket számol, observability correlation id-t illeszt, details payloadot sanitizál, majd szinkron módon az AuditLogRepository append műveletére delegál. Közös audit szolgáltatás auth, users, settings, brand, tenant, admin és event folyamatokhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from typing import Any

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.kernel.logging.observability import get_observability_context
from core.infrastructure.audit.repositories.audit_log_repository import AuditLogRepository
from shared.utils import sanitize_log_data


class AuditService:
    
    # Audit log repository inicializálása
    def __init__(self, repo: AuditLogRepository):
        self._repo = repo

    # Audit log rögzítése
    def log(
        self,
        action: AuditLogAction,
        *,
        user_id: int | None = None,
        actor_type: str | None = None,
        event_name: str | None = None,
        outcome: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        ctx = get_observability_context()
        self._repo.append(
            action=action,
            user_id=user_id,
            actor_type=actor_type or ("user" if user_id is not None else "system"),
            event_name=event_name or str(action),
            outcome=outcome or self._default_outcome(action),
            target_type=target_type or self._default_target_type(action, user_id=user_id),
            target_id=target_id or (str(user_id) if user_id is not None else None),
            correlation_id=correlation_id or ctx.get("correlation_id"),
            details=sanitize_log_data(details),
            ip=ip,
            user_agent=user_agent,
        )

    @staticmethod
    def _default_outcome(action: AuditLogAction) -> str:
        action_name = str(action)
        if action_name.endswith("_failed") or action_name.endswith("_error"):
            return "failure"
        if action == AuditLogAction.LOGIN_2FA_REQUIRED:
            return "challenge_required"
        if action == AuditLogAction.LOGIN_2FA_RATE_LIMITED:
            return "rate_limited"
        return "success"

    @staticmethod
    def _default_target_type(action: AuditLogAction, *, user_id: int | None) -> str | None:
        if user_id is not None:
            return "user"
        if action in {AuditLogAction.SETTINGS_SECURITY_UPDATED}:
            return "platform_settings"
        if action in {AuditLogAction.BRAND_UPDATED}:
            return "platform_brand"
        if action in {AuditLogAction.TENANT_PROVISIONED}:
            return "tenant"
        if str(action).startswith("platform_admin_"):
            return "platform_admin"
        return None
