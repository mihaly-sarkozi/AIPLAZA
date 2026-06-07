from __future__ import annotations

from enum import Enum


class TrainingBatchStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"


__all__ = ["TrainingBatchStatus"]
