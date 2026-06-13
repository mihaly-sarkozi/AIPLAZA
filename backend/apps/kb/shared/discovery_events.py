from __future__ import annotations

from core.kernel.jobs import enqueue_job

from apps.kb.shared.events import DISCOVERY_REQUESTED


def enqueue_discovery_requested(
    *,
    tenant_slug: str | None,
    knowledge_base_id: str,
    training_batch_id: str,
    training_item_id: str,
    understanding_job_id: str,
    created_by: int | None,
) -> None:
    enqueue_job(
        DISCOVERY_REQUESTED,
        {
            "tenant_slug": tenant_slug,
            "knowledge_base_id": knowledge_base_id,
            "training_batch_id": training_batch_id,
            "training_item_id": training_item_id,
            "understanding_job_id": understanding_job_id,
            "created_by": created_by,
        },
        idempotency_key=f"{DISCOVERY_REQUESTED}:{tenant_slug or '_'}:{understanding_job_id}",
    )


__all__ = ["enqueue_discovery_requested"]
