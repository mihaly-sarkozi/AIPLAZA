from __future__ import annotations

from enum import Enum


class IndexVerificationItemStatus(str, Enum):
    VERIFIED = "VERIFIED"
    MISSING_POINT = "MISSING_POINT"
    PAYLOAD_MISMATCH = "PAYLOAD_MISMATCH"
    VECTOR_MISMATCH = "VECTOR_MISMATCH"
    FAILED = "FAILED"


__all__ = ["IndexVerificationItemStatus"]
