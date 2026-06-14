from __future__ import annotations

from enum import Enum


class IndexRebuildStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


TERMINAL_REBUILD_STATUSES = frozenset(
    {
        IndexRebuildStatus.COMPLETED,
        IndexRebuildStatus.PARTIAL,
        IndexRebuildStatus.FAILED,
    }
)


__all__ = ["TERMINAL_REBUILD_STATUSES", "IndexRebuildStatus"]
