from __future__ import annotations

from enum import Enum


class EmbeddingStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


TERMINAL_STATUSES = frozenset(
    {
        EmbeddingStatus.COMPLETED,
        EmbeddingStatus.PARTIAL,
        EmbeddingStatus.FAILED,
    }
)


__all__ = ["TERMINAL_STATUSES", "EmbeddingStatus"]
