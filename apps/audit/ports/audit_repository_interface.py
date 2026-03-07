# apps/audit/ports/audit_repository_interface.py
# Audit log rögzítése a táblába. Interface.
# 2026.03.07 - Sárközi Mihály

from abc import ABC, abstractmethod
from typing import Optional


class AuditRepositoryInterface(ABC):
    @abstractmethod
    def append(
        self,
        action: str,
        user_id: Optional[int] = None,
        details: Optional[str] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Egy audit esemény rögzítése (tenant sémában)."""
        ...
