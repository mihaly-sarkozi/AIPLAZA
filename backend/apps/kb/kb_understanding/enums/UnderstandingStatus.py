from __future__ import annotations

from enum import Enum


class UnderstandingStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    EXTRACTING = "extracting"
    NORMALIZING = "normalizing"
    CHUNKING = "chunking"
    VALIDATING = "validating"
    READY_FOR_DISCOVERY = "ready_for_discovery"
    PARTIAL = "partial"
    FAILED = "failed"
    RETRYABLE = "retryable"


TERMINAL_STATUSES = frozenset(
    {
        UnderstandingStatus.READY_FOR_DISCOVERY,
        UnderstandingStatus.PARTIAL,
        UnderstandingStatus.FAILED,
        UnderstandingStatus.RETRYABLE,
    }
)


__all__ = ["TERMINAL_STATUSES", "UnderstandingStatus"]
