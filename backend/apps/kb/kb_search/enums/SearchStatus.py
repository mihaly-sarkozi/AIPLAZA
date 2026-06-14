from __future__ import annotations

from enum import Enum


class SearchStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    NO_RESULTS = "NO_RESULTS"
    FAILED = "FAILED"
    BLOCKED_NOT_READY = "BLOCKED_NOT_READY"


__all__ = ["SearchStatus"]
