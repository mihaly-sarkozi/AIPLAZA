from __future__ import annotations

from enum import Enum


class SearchResultType(str, Enum):
    CHUNK = "chunk"
    DOCUMENT = "document"


__all__ = ["SearchResultType"]
