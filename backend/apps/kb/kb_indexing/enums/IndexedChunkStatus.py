from __future__ import annotations

from enum import Enum


class IndexedChunkStatus(str, Enum):
    PENDING = "PENDING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    DELETED = "DELETED"
    REMOVED = "REMOVED"
    REPLACED = "REPLACED"
    DELETE_FAILED = "DELETE_FAILED"


__all__ = ["IndexedChunkStatus"]
