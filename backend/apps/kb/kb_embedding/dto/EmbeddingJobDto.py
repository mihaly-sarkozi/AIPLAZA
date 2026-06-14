from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EmbeddingJobDto:
    id: str
    status: str
    knowledge_base_id: str
    training_item_id: str
    discovery_job_id: str
    chunks_total: int = 0
    chunks_embedded: int = 0
    chunks_failed: int = 0
    embedding_model: str = ""
    embedding_provider: str = ""
    embedding_dimension: int = 0
    error_code: str | None = None
    error_message: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


__all__ = ["EmbeddingJobDto"]
