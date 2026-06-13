from __future__ import annotations

from enum import Enum


class ProcessingEventStatus(str, Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


__all__ = ["ProcessingEventStatus"]
