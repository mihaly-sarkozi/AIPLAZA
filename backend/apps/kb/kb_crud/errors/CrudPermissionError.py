from __future__ import annotations

# backend/apps/kb/kb_crud/errors/CrudPermissionError.py
# Feladat: Nyelvfüggetlen tudástár jogosultsági hiba.
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.shared.errors import KbPermissionError


class CrudPermissionError(KbPermissionError):
    def __init__(self, code: CrudErrorCode = CrudErrorCode.PERMISSION_DENIED) -> None:
        self.code = code.value
        super().__init__(self.code)


__all__ = ["CrudPermissionError"]
