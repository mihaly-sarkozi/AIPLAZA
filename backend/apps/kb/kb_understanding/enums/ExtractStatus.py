from __future__ import annotations

from enum import Enum


class ExtractStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    PARTIAL_TIMEOUT = "partial_timeout"
    FAILED = "failed"


__all__ = ["ExtractStatus"]
