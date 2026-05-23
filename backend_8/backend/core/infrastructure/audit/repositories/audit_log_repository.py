# backend/core/infrastructure/audit/repositories/audit_log_repository.py
# Feladat: Append-only audit log repository adapter. Session factoryval AuditLogORM sort hoz létre, JSON details mezőt serializál, majd commitolja az eseményt az aktuális tenant schema audit_log táblájába. Audit perzisztencia adapter az AuditService alatt.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.infrastructure.audit.models.audit_log_orm import AuditLogORM


class AuditLogRepository:
    
    # Audit log repository inicializálása
    def __init__(self, session_factory: Callable[[], AbstractContextManager[Any]]):
        self._sf = session_factory

    # Audit log rögzítése a táblába
    def append(
        self,
        *,
        action: AuditLogAction,
        user_id: int | None = None,
        actor_type: str = "system",
        event_name: str | None = None,
        outcome: str | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        correlation_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        details_str = None if details is None else json.dumps(details, ensure_ascii=False)
        with self._sf() as db:
            row = AuditLogORM(
                user_id=user_id,
                actor_type=actor_type,
                action=action,
                event_name=event_name,
                outcome=outcome,
                target_type=target_type,
                target_id=target_id,
                correlation_id=correlation_id,
                details=details_str,
                ip=ip,
                user_agent=user_agent,
            )
            db.add(row)
            db.commit()
