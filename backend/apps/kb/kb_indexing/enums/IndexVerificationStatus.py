from __future__ import annotations

from enum import Enum


class IndexVerificationStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


__all__ = ["IndexVerificationStatus"]
