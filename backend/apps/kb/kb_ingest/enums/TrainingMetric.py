from __future__ import annotations

from enum import Enum


class TrainingMetric(str, Enum):
    """Tanítási metrika nevek (nyelvfüggetlen azonosítók)."""

    BATCH_CREATED = "kb.training.batch.created"
    BATCH_COMPLETED = "kb.training.batch.completed"
    ITEM_ACCEPTED = "kb.training.item.accepted"
    STORAGE_WRITE = "kb.training.storage.write"
    UNDERSTANDING_REQUESTED = "kb.training.understanding.requested"


__all__ = ["TrainingMetric"]
