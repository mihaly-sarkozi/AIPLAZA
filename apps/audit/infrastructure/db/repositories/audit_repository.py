# apps/audit/infrastructure/db/repositories/audit_repository.py
# Audit log rögzítése a táblába.
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations
from typing import Optional

from apps.audit.infrastructure.db.models import AuditLogORM
from apps.audit.ports import AuditRepositoryInterface


class AuditRepository(AuditRepositoryInterface):
    def __init__(self, session_factory):
        self._sf = session_factory

    def append(
        self,
        action: str,
        user_id: Optional[int] = None,
        details: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        with self._sf() as db:
            row = AuditLogORM(
                user_id=user_id,
                action=action,
                details=details,
                ip=ip,
                user_agent=user_agent,
            )
            db.add(row)
            db.commit()
