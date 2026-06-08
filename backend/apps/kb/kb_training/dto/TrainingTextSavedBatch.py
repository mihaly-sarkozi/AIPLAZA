from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TrainingTextSavedBatch:
    batch_id: str
    item_id: str
    created_at: datetime
    completed_at: datetime | None


__all__ = ["TrainingTextSavedBatch"]
