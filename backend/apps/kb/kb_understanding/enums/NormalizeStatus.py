from __future__ import annotations

from enum import Enum


class NormalizeStatus(str, Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


__all__ = ["NormalizeStatus"]
