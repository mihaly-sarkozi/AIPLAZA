from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndexedChunkDto:
    id: str
    chunk_id: str
    embedding_id: str
    qdrant_collection: str
    qdrant_point_id: str
    status: str
    payload_hash: str | None = None
    vector_hash: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


__all__ = ["IndexedChunkDto"]
