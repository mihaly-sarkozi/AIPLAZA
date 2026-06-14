from __future__ import annotations

from enum import Enum


class SearchMode(str, Enum):
    VECTOR = "vector"
    HYBRID = "hybrid"


__all__ = ["SearchMode"]
