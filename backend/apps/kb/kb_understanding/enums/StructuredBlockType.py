from __future__ import annotations

# backend/apps/kb/kb_understanding/enums/StructuredBlockType.py
# Feladat: A struktúrafelismerés blokktípusai.
# Sárközi Mihály - 2026.06.11

from enum import Enum


class StructuredBlockType(str, Enum):
    TITLE = "title"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    TABLE = "table"
    FAQ = "faq"
    STEP = "step"
    NOTE = "note"
    WARNING = "warning"


__all__ = ["StructuredBlockType"]
