from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IndexingJobContext:
    job_id: str
    understanding_job_id: str
    discovery_job_id: str
    embedding_job_id: str
    training_item_id: str
    training_batch_id: str
    knowledge_base_id: str
    tenant_slug: str | None
    created_by: int | None
    collection_name: str
    vector_size: int
    distance_metric: str
    title: str
    source_type: str


__all__ = ["IndexingJobContext"]
