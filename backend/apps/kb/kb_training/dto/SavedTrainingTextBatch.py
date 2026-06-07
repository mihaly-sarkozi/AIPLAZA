from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SavedTrainingTextBatch:
    batch_id: str
    item_id: str


__all__ = ["SavedTrainingTextBatch"]
