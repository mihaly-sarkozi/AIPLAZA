from __future__ import annotations

from enum import Enum


class ExtractStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


__all__ = ["ExtractStatus"]
