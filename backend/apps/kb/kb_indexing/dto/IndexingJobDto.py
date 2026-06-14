from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IndexingJobDto:
    id: str
    status: str
    knowledge_base_id: str
    training_item_id: str
    embedding_job_id: str
    collection_name: str = ""
    vector_size: int = 0
    chunks_total: int = 0
    chunks_indexed: int = 0
    chunks_failed: int = 0
    error_code: str | None = None
    error_message: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


__all__ = ["IndexingJobDto"]
