from __future__ import annotations

from apps.kb.shared.events import EMBEDDING_REQUESTED
from core.kernel.jobs import enqueue_job


def add_embedding_requested_event(
    *,
    tenant_slug: str | None,
    knowledge_base_id: str,
    training_item_id: str,
    understanding_job_id: str,
    discovery_job_id: str,
    created_by: int | None,
) -> None:
    enqueue_job(
        EMBEDDING_REQUESTED,
        {
            "tenant_slug": tenant_slug,
            "knowledge_base_id": knowledge_base_id,
            "training_item_id": training_item_id,
            "understanding_job_id": understanding_job_id,
            "discovery_job_id": discovery_job_id,
            "created_by": created_by,
        },
        idempotency_key=f"{EMBEDDING_REQUESTED}:{tenant_slug or '_'}:{discovery_job_id}",
    )


__all__ = ["add_embedding_requested_event"]
