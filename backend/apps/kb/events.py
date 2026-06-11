from __future__ import annotations

# backend/apps/kb/events.py
# Feladat: KB outbox worker handler regisztráció (modulhatárokon átívelő wiring).
# A kb_understanding modul eltávolításáig a handler csak naplóz, hogy a
# kb_ingest által sorba tett események ne ragadjanak be az outboxban.
# Sárközi Mihály - 2026.06.07

import logging
from typing import Any

from core.kernel.jobs import register_job_handler

from apps.kb.shared.events import UNDERSTANDING_REQUESTED

logger = logging.getLogger(__name__)


def make_kb_understanding_requested_handler():
    """Outbox handler: kb.understanding_requested → ideiglenes no-op."""

    def _handle(payload: dict[str, Any]) -> None:
        logger.info(
            "kb.understanding_requested skipped: understanding module not installed (item=%s)",
            payload.get("training_item_id"),
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
