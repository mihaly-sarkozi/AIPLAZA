from __future__ import annotations

from enum import Enum


class ExtractPartType(str, Enum):
    TEXT = "TEXT"
    TABLE = "TABLE"
    OCR_TEXT = "OCR_TEXT"
    OCR_EMPTY = "OCR_EMPTY"
    OCR_FAILED = "OCR_FAILED"
    HEADER = "HEADER"
    FOOTER = "FOOTER"
    UNKNOWN = "UNKNOWN"


NORMALIZABLE_PART_TYPES = frozenset(
    {
        ExtractPartType.TEXT,
        ExtractPartType.TABLE,
        ExtractPartType.OCR_TEXT,
        ExtractPartType.HEADER,
        ExtractPartType.FOOTER,
    }
)


__all__ = ["ExtractPartType", "NORMALIZABLE_PART_TYPES"]
