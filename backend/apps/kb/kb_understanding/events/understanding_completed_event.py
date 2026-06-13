from __future__ import annotations

from apps.kb.shared.events import UNDERSTANDING_COMPLETED
from core.kernel.jobs import enqueue_job


def add_understanding_completed_event(
    *,
    tenant_slug: str | None,
    job_id: str,
    training_item_id: str,
    training_batch_id: str,
    knowledge_base_id: str,
    created_by: int | None,
    status: str,
) -> None:
    enqueue_job(
        UNDERSTANDING_COMPLETED,
        {
            "tenant_slug": tenant_slug,
            "understanding_job_id": job_id,
            "training_item_id": training_item_id,
            "training_batch_id": training_batch_id,
            "knowledge_base_id": knowledge_base_id,
            "created_by": created_by,
            "status": status,
        },
        idempotency_key=f"{UNDERSTANDING_COMPLETED}:{tenant_slug or '_'}:{job_id}",
    )


__all__ = ["add_understanding_completed_event"]
