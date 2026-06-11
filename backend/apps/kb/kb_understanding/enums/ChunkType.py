from __future__ import annotations

# backend/apps/kb/kb_understanding/enums/ChunkType.py
# Feladat: A tudás-chunkok típusai (a domináns forrásblokk szerint).
# Sárközi Mihály - 2026.06.11

from enum import Enum


class ChunkType(str, Enum):
    TEXT = "text"
    LIST = "list"
    TABLE = "table"
    FAQ = "faq"
    STEP = "step"
    NOTE = "note"
    WARNING = "warning"


__all__ = ["ChunkType"]
