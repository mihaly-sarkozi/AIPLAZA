from __future__ import annotations

# backend/apps/kb/kb_ingest/errors/TrainingQueueUnavailableError.py
# Feladat: Outbox / worker queue nem elérhető — a tanítás mentve, de a feldolgozás nem indult.
# Sárközi Mihály - 2026.06.07

from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.shared.errors import KbProcessingError


class TrainingQueueUnavailableError(KbProcessingError):
    def __init__(self) -> None:
        self.code = TrainingErrorCode.QUEUE_UNAVAILABLE.value
        self.params: dict[str, object] = {}
        super().__init__(self.code)


__all__ = ["TrainingQueueUnavailableError"]
