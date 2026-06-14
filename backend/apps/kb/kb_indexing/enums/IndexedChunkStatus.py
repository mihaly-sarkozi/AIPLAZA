from __future__ import annotations

from enum import Enum


class IndexedChunkStatus(str, Enum):
    PENDING = "PENDING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    DELETED = "DELETED"


__all__ = ["IndexedChunkStatus"]
