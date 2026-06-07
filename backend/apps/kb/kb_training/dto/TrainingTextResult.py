from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_training.enums.TrainingBatchStatus import TrainingBatchStatus


@dataclass(frozen=True)
class TrainingTextResult:
    training_batch_id: str
    status: TrainingBatchStatus


__all__ = ["TrainingTextResult"]
