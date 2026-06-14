from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EmbeddingRecordDto:
    id: str
    chunk_id: str
    embedding_job_id: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int
    embedding_vector: list[float] | None
    vector_hash: str | None
    content_hash: str | None
    embedding_input_hash: str | None
    status: str
    error_code: str | None = None
    error_message: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


__all__ = ["EmbeddingRecordDto"]
