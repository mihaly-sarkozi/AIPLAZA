from __future__ import annotations

# backend/apps/kb/kb_understanding/events/understanding_completed_event.py
# Feladat: Megértés lezárult (READY_FOR_INDEXING / PARTIAL) esemény írása a job queue-ba.
# Sárközi Mihály - 2026.06.11

from apps.kb.shared.events import UNDERSTANDING_COMPLETED
from core.kernel.jobs import enqueue_job


def add_understanding_completed_event(
    *,
    tenant_slug: str | None,
    job_id: str,
    training_item_id: str,
    knowledge_base_id: str,
    status: str,
) -> None:
    enqueue_job(
        UNDERSTANDING_COMPLETED,
        {
            "tenant_slug": tenant_slug,
            "understanding_job_id": job_id,
            "training_item_id": training_item_id,
            "knowledge_base_id": knowledge_base_id,
            "status": status,
        },
        idempotency_key=f"{UNDERSTANDING_COMPLETED}:{tenant_slug or '_'}:{job_id}",
    )


__all__ = ["add_understanding_completed_event"]
