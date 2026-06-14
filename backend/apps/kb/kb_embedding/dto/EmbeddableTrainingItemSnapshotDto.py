from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EmbeddableTrainingItemSnapshotDto:
    training_item_id: str
    knowledge_base_id: str
    embedding_job_id: str
    discovery_job_id: str
    understanding_job_id: str
    status: str
    embedding_model: str
    embedding_provider: str
    embedding_dimension: int
    chunks_embedded: int
    chunks_failed: int
    created_at: datetime | None
    finished_at: datetime | None


__all__ = ["EmbeddableTrainingItemSnapshotDto"]
