from __future__ import annotations

# backend/apps/kb/kb_ingest/errors/TrainingDuplicateError.py
# Feladat: Ugyanolyen tartalom már létezik a tudástárban (409 Conflict).
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.shared.errors import KbValidationError


class TrainingDuplicateError(KbValidationError):
    def __init__(self) -> None:
        self.code = TrainingErrorCode.DUPLICATE_CONTENT.value
        self.params: dict[str, object] = {}
        super().__init__(self.code)


__all__ = ["TrainingDuplicateError"]
