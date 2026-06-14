from __future__ import annotations

from apps.kb.shared.events import INDEXING_COMPLETED
from core.kernel.jobs import enqueue_job


def add_indexing_completed_event(
    *,
    tenant_slug: str | None,
    knowledge_base_id: str,
    training_item_id: str,
    understanding_job_id: str,
    discovery_job_id: str,
    embedding_job_id: str,
    indexing_job_id: str,
    status: str,
    created_by: int | None,
) -> None:
    enqueue_job(
        INDEXING_COMPLETED,
        {
            "tenant_slug": tenant_slug,
            "knowledge_base_id": knowledge_base_id,
            "training_item_id": training_item_id,
            "understanding_job_id": understanding_job_id,
            "discovery_job_id": discovery_job_id,
            "embedding_job_id": embedding_job_id,
            "indexing_job_id": indexing_job_id,
            "status": status,
            "created_by": created_by,
        },
        idempotency_key=f"{INDEXING_COMPLETED}:{tenant_slug or '_'}:{indexing_job_id}",
    )


__all__ = ["add_indexing_completed_event"]
