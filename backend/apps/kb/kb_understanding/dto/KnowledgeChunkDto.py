from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/KnowledgeChunkDto.py
# Feladat: A chunking lépés kimenete — egy kereshető tudás-chunk tartalma + forráshelye.
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass, field
from typing import Any

from apps.kb.kb_understanding.enums.ChunkType import ChunkType


@dataclass(frozen=True)
class KnowledgeChunkDto:
    # Perzisztáláskor kiosztott azonosító (chunk_…); a mapper tölti.
    chunk_id: str
    text: str
    chunk_type: ChunkType
    order_index: int
    token_count: int
    checksum: str
    page_number: int | None = None
    section_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["KnowledgeChunkDto"]
