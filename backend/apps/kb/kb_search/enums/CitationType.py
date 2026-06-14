from __future__ import annotations

from enum import Enum


class CitationType(str, Enum):
    CHUNK = "chunk"
    DOCUMENT = "document"
    SECTION = "section"


__all__ = ["CitationType"]
