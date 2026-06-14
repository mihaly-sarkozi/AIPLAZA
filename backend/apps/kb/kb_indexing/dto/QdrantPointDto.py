from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QdrantPointDto:
    point_id: str
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)
    payload_hash: str = ""
    vector_hash: str = ""
    chunk_id: str = ""
    embedding_id: str = ""


__all__ = ["QdrantPointDto"]
