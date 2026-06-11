from __future__ import annotations

# backend/apps/kb/kb_ingest/errors/TrainingNotFoundError.py
# Feladat: Nyelvfüggetlen tanítási batch nem található hiba.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.shared.errors import KbNotFoundError


class TrainingNotFoundError(KbNotFoundError):
    def __init__(self, code: TrainingErrorCode) -> None:
        self.code = code.value
        super().__init__(self.code)


__all__ = ["TrainingNotFoundError"]
