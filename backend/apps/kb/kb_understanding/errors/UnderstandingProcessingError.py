from __future__ import annotations

# backend/apps/kb/kb_understanding/errors/UnderstandingProcessingError.py
# Feladat: Nyelvfüggetlen megértési feldolgozási hiba (kód + retryable jelzés).
# Sárközi Mihály - 2026.06.11

from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.shared.errors import KbProcessingError


class UnderstandingProcessingError(KbProcessingError):
    def __init__(self, code: UnderstandingErrorCode, *, retryable: bool = False, **params: object) -> None:
        self.code = code.value
        self.retryable = retryable
        self.params = params
        super().__init__(self.code)


__all__ = ["UnderstandingProcessingError"]
