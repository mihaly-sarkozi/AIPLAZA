from __future__ import annotations

# backend/apps/kb/kb_understanding/events/understanding_requested_event.py
# Feladat: Megértési feldolgozás újra-sorbaállítása (retry) a platform job queue-ba.
# Az idempotency kulcs tartalmazza a retry sorszámot, hogy ne ütközzön a korábbi jobbal.
# Sárközi Mihály - 2026.06.11

from apps.kb.shared.events import UNDERSTANDING_REQUESTED
from core.kernel.jobs import enqueue_job


def add_understanding_retry_event(
    *,
    tenant_slug: str | None,
    training_batch_id: str,
    training_item_id: str,
    knowledge_base_id: str,
    created_by: int | None,
    retry_count: int,
) -> None:
    enqueue_job(
        UNDERSTANDING_REQUESTED,
        {
            "tenant_slug": tenant_slug,
            "training_batch_id": training_batch_id,
            "training_item_id": training_item_id,
            "knowledge_base_id": knowledge_base_id,
            "created_by": created_by,
        },
        idempotency_key=(
            f"{UNDERSTANDING_REQUESTED}:{tenant_slug or '_'}:{training_item_id}:retry:{retry_count}"
        ),
    )


__all__ = ["add_understanding_retry_event"]
