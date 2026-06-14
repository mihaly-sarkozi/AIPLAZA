from __future__ import annotations

from enum import Enum


class IndexingStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


TERMINAL_STATUSES = frozenset(
    {
        IndexingStatus.COMPLETED,
        IndexingStatus.PARTIAL,
        IndexingStatus.FAILED,
    }
)


__all__ = ["TERMINAL_STATUSES", "IndexingStatus"]
