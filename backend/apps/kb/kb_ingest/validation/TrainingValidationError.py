from __future__ import annotations

# backend/apps/kb/kb_ingest/validation/TrainingValidationError.py
# Feladat: Nyelvfüggetlen tanítási validációs hiba (kód + opcionális paraméterek).
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.shared.errors import KbValidationError


class TrainingValidationError(KbValidationError):
    def __init__(self, code: TrainingErrorCode, **params: object) -> None:
        self.code = code.value
        self.params = params
        super().__init__(self.code)


__all__ = ["TrainingValidationError"]
