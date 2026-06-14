from __future__ import annotations

from enum import Enum


class IndexRebuildMode(str, Enum):
    POINT_DELETE_AND_REINDEX = "POINT_DELETE_AND_REINDEX"
    RECREATE_COLLECTION = "RECREATE_COLLECTION"


__all__ = ["IndexRebuildMode"]
