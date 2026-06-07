from __future__ import annotations

# backend/apps/kb/kb_crud/errors/CrudNotFoundError.py
# Feladat: Nyelvfüggetlen tudástár nem található hiba.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_crud.domain.CrudErrorCode import CrudErrorCode
from apps.kb.shared.errors import KbNotFoundError


class CrudNotFoundError(KbNotFoundError):
    def __init__(self, code: CrudErrorCode) -> None:
        self.code = code.value
        super().__init__(self.code)


__all__ = ["CrudNotFoundError"]
