from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apps.kb.kb_ingest.enums.TrainingBatchStatus import TrainingBatchStatus


@dataclass(frozen=True)
class TrainingTextResult:
    """Service réteg visszatérés — belső használatra (`TrainingTextResponse` előállításához)."""
    training_batch_id: str
    status: TrainingBatchStatus
    created_at: datetime
    completed_at: datetime | None


__all__ = ["TrainingTextResult"]
