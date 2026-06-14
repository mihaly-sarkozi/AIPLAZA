from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingInputDto:
    chunk_id: str
    input_text: str
    input_hash: str
    content_hash: str


__all__ = ["EmbeddingInputDto"]
