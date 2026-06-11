from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/StructuredBlockDto.py
# Feladat: A struktúrafelismerés egy blokkja.
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass

from apps.kb.kb_understanding.enums.StructuredBlockType import StructuredBlockType


@dataclass(frozen=True)
class StructuredBlockDto:
    block_type: StructuredBlockType
    text: str
    order_index: int
    page_number: int | None = None
    section_title: str | None = None


__all__ = ["StructuredBlockDto"]
