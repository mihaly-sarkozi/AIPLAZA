from __future__ import annotations

# backend/apps/kb/events.py
# Feladat: KB outbox worker handler regisztráció (modulhatárokon átívelő wiring).
# Kompozíciós gyökér: itt köthető össze a kb_understanding pipeline a kb_ingest
# item-olvasó adapterével. Az INDEXING_REQUESTED-hez ideiglenes no-op acknowledger
# fut, amíg a kb_indexing modul el nem készül.
# Sárközi Mihály - 2026.06.07

import logging
import threading
from typing import Any

from core.kernel.jobs import register_job_handler

from apps.kb.shared.events import (
    INDEXING_REQUESTED,
    UNDERSTANDING_COMPLETED,
    UNDERSTANDING_FAILED,
    UNDERSTANDING_REQUESTED,
)

logger = logging.getLogger(__name__)


def make_understanding_services_provider(session_factory: Any):
    """Lazy, cache-elt UnderstandingServices gyár.

    ``session_factory``: web processben a container-é, worker processben az
    entrypoint infrastruktúrájáé.
    """
    lock = threading.Lock()
    cache: dict[str, Any] = {}

    def _provider():
        if session_factory is None:
            raise RuntimeError("kb understanding handler: hiányzó session_factory")
        with lock:
            if "services" not in cache:
                from apps.kb.kb_ingest.adapters.TrainingItemReader import TrainingItemReader
                from apps.kb.kb_understanding.bootstrap.understanding_assembly import (
                    build_understanding_services,
                )
                from infra.kb import MinioFileStorage

                cache["services"] = build_understanding_services(
                    session_factory=session_factory,
                    file_storage=MinioFileStorage(),
                    item_reader=TrainingItemReader(session_factory),
                )
            return cache["services"]

    return _provider


def make_kb_acknowledge_handler(event_type: str):
    """Ideiglenes no-op handler: az esemény ne ragadjon be az outboxban."""

    def _handle(payload: dict[str, Any]) -> None:
        logger.info(
            "%s acknowledged (item=%s job=%s)",
            event_type,
            payload.get("training_item_id"),
            payload.get("understanding_job_id"),
        )

    return _handle


def register_kb_event_handlers(dispatcher: Any, *, session_factory: Any = None) -> None:
    """Regisztrálja a KB outbox handler-eket a platform dispatcher-be."""
    from apps.kb.kb_understanding.events.understanding_requested_handler import (
        make_understanding_requested_handler,
    )

    register_job_handler(
        dispatcher,
        UNDERSTANDING_REQUESTED,
        make_understanding_requested_handler(
            make_understanding_services_provider(session_factory)
        ),
    )
    # A kb_indexing modul elkészültéig no-op acknowledger fut ezekre.
    register_job_handler(dispatcher, INDEXING_REQUESTED, make_kb_acknowledge_handler(INDEXING_REQUESTED))
    register_job_handler(
        dispatcher, UNDERSTANDING_COMPLETED, make_kb_acknowledge_handler(UNDERSTANDING_COMPLETED)
    )
    register_job_handler(
        dispatcher, UNDERSTANDING_FAILED, make_kb_acknowledge_handler(UNDERSTANDING_FAILED)
    )


__all__ = [
    "make_kb_acknowledge_handler",
    "make_understanding_services_provider",
    "register_kb_event_handlers",
]
