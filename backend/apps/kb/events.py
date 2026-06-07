from __future__ import annotations

# backend/apps/kb/events.py
# Feladat: KB outbox worker handler regisztráció (modulhatárokon átívelő wiring).
# Sárközi Mihály - 2026.06.07

from typing import Any

from core.kernel.jobs import register_job_handler

from apps.kb.jobs.process_training_understanding import process_training_understanding_sync
from apps.kb.shared.events import UNDERSTANDING_REQUESTED


def make_kb_understanding_requested_handler():
    """Outbox handler: kb.understanding_requested → DB-ből betölt, understanding indul."""

    def _handle(payload: dict[str, Any]) -> None:
        tenant_slug = payload.get("tenant_slug")
        training_item_id = str(payload.get("training_item_id") or "").strip()
        created_by = payload.get("created_by")
        if not training_item_id:
            raise ValueError(f"{UNDERSTANDING_REQUESTED} payload missing training_item_id")
        process_training_understanding_sync(
            tenant_slug=tenant_slug if tenant_slug is None else str(tenant_slug),
            training_item_id=training_item_id,
            created_by=int(created_by) if created_by is not None else None,
        )

    return _handle


def register_kb_event_handlers(dispatcher: Any) -> None:
    """Regisztrálja a KB outbox handler-eket a platform dispatcher-be."""
    register_job_handler(
        dispatcher,
        UNDERSTANDING_REQUESTED,
        make_kb_understanding_requested_handler(),
    )


__all__ = ["register_kb_event_handlers"]
