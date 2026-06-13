from __future__ import annotations

from apps.kb.shared.events import DISCOVERY_FAILED
from core.kernel.jobs import enqueue_job


def add_discovery_failed_event(
    *,
    tenant_slug: str | None,
    job_id: str,
    understanding_job_id: str,
    training_item_id: str,
    knowledge_base_id: str,
    status: str,
    error_code: str,
) -> None:
    enqueue_job(
        DISCOVERY_FAILED,
        {
            "tenant_slug": tenant_slug,
            "discovery_job_id": job_id,
            "understanding_job_id": understanding_job_id,
            "training_item_id": training_item_id,
            "knowledge_base_id": knowledge_base_id,
            "status": status,
            "error_code": error_code,
        },
        idempotency_key=f"{DISCOVERY_FAILED}:{tenant_slug or '_'}:{job_id}:{error_code}",
    )


__all__ = ["add_discovery_failed_event"]
