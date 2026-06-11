from __future__ import annotations

# backend/apps/kb/kb_understanding/events/indexing_requested_event.py
# Feladat: Sikeres megértés után indexelési kérés írása a platform job queue-ba.
# Sárközi Mihály - 2026.06.11

from apps.kb.shared.events import INDEXING_REQUESTED
from core.kernel.jobs import enqueue_job


def add_indexing_requested_event(
    *,
    tenant_slug: str | None,
    job_id: str,
    training_item_id: str,
    knowledge_base_id: str,
) -> None:
    enqueue_job(
        INDEXING_REQUESTED,
        {
            "tenant_slug": tenant_slug,
            "understanding_job_id": job_id,
            "training_item_id": training_item_id,
            "knowledge_base_id": knowledge_base_id,
        },
        idempotency_key=f"{INDEXING_REQUESTED}:{tenant_slug or '_'}:{job_id}",
    )


__all__ = ["add_indexing_requested_event"]
