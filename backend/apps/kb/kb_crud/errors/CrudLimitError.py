from __future__ import annotations

# backend/apps/kb/kb_crud/errors/CrudLimitError.py
# Feladat: Tudástár létrehozási limit hiba — a billing/usage rétegtől kapott
# (lokalizált) indoklást is hordozza, hogy a kliens változatlanul megkapja.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.shared.errors import KbValidationError


class CrudLimitError(KbValidationError):
    def __init__(self, reason: str | None = None) -> None:
        self.code = CrudErrorCode.KB_LIMIT_REACHED.value
        self.reason = reason
        super().__init__(reason or self.code)


__all__ = ["CrudLimitError"]
