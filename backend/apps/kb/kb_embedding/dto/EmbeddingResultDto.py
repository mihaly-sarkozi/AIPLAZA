from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingResultDto:
    chunk_id: str
    vector: list[float]
    vector_hash: str
    input_hash: str
    content_hash: str
    dimension: int
    skipped: bool = False


__all__ = ["EmbeddingResultDto"]
