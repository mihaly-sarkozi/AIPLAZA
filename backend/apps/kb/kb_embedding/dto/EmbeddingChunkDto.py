from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EmbeddingChunkDto:
    chunk_id: str
    text: str
    chunk_type: str
    order_index: int
    section_title: str | None = None
    page_number: int | None = None
    language_code: str | None = None
    language_confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["EmbeddingChunkDto"]
