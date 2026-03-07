# apps/audit/application/audit_service.py
# Teljes audit log: belépés (siker/sikertelen), 2FA, kilépés, refresh, user CRUD.
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations
import json
from typing import Optional, Any

from apps.audit.ports import AuditRepositoryInterface


class AuditService:
    """Egy táblába írja az összes audit eseményt (tenant sémában)."""

    def __init__(self, repo: AuditRepositoryInterface):
        self._repo = repo

    def log(
        self,
        action: str,
        user_id: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Egy esemény rögzítése. details dict-et JSON stringként tároljuk."""
        details_str = json.dumps(details, ensure_ascii=False) if details else None
        self._repo.append(
            action=action,
            user_id=user_id,
            details=details_str,
            ip=ip,
            user_agent=user_agent,
        )
