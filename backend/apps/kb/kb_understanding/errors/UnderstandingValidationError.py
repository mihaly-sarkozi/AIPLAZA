from __future__ import annotations

# backend/apps/kb/kb_understanding/errors/UnderstandingValidationError.py
# Feladat: Nyelvfüggetlen megértési validációs hiba (kód + opcionális paraméterek).
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.shared.errors import KbValidationError


class UnderstandingValidationError(KbValidationError):
    def __init__(self, code: UnderstandingErrorCode, **params: object) -> None:
        self.code = code.value
        self.params = params
        super().__init__(self.code)


__all__ = ["UnderstandingValidationError"]
