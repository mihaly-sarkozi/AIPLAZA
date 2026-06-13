from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto


@dataclass(frozen=True)
class ChunkContentResultDto:
    chunks: list[KnowledgeChunkDto] = field(default_factory=list)
    trace_summary: dict[str, Any] = field(default_factory=dict)


__all__ = ["ChunkContentResultDto"]
