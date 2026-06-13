from __future__ import annotations

import logging
import threading
from typing import Any

from core.kernel.jobs import register_job_handler

from apps.kb.shared.events import (
    DISCOVERY_COMPLETED,
    DISCOVERY_FAILED,
    DISCOVERY_REQUESTED,
    EMBEDDING_REQUESTED,
    INDEXING_REQUESTED,
    UNDERSTANDING_COMPLETED,
    UNDERSTANDING_FAILED,
    UNDERSTANDING_REQUESTED,
)

logger = logging.getLogger(__name__)


def make_understanding_services_provider(session_factory: Any):
    lock = threading.Lock()
    cache: dict[str, Any] = {}

    def _provider():
        if session_factory is None:
            raise RuntimeError("kb understanding handler: hiányzó session_factory")
        with lock:
            if "services" not in cache:
                from apps.kb.kb_ingest.adapters.TrainingItemReader import TrainingItemReader
                from apps.kb.kb_processing.bootstrap.processing_assembly import build_processing_services
                from apps.kb.kb_understanding.bootstrap.understanding_assembly import (
                    build_understanding_services,
                )
                from infra.kb import MinioFileStorage

                processing = build_processing_services(session_factory=session_factory)
                cache["services"] = build_understanding_services(
                    session_factory=session_factory,
                    file_storage=MinioFileStorage(),
                    item_reader=TrainingItemReader(session_factory),
                    flow_recorder=processing.flow_recorder,
                )
            return cache["services"]

    return _provider


def make_discovery_services_provider(session_factory: Any):
    lock = threading.Lock()
    cache: dict[str, Any] = {}

    def _provider():
        if session_factory is None:
            raise RuntimeError("kb discovery handler: hiányzó session_factory")
        with lock:
            if "services" not in cache:
                from apps.kb.bootstrap.discovery_wiring import (
                    ChunkLanguageWriterAdapter,
                    ChunkReaderAdapter,
                    UnderstandingJobReaderAdapter,
                )
                from apps.kb.kb_discovery.bootstrap.discovery_assembly import build_discovery_services
                from apps.kb.kb_processing.bootstrap.processing_assembly import build_processing_services
                from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
                from apps.kb.kb_understanding.repository.UnderstandingJobRepository import (
                    UnderstandingJobRepository,
                )

                chunk_repository = ChunkRepository(session_factory)
                processing = build_processing_services(session_factory=session_factory)
                cache["services"] = build_discovery_services(
                    session_factory=session_factory,
                    chunk_reader=ChunkReaderAdapter(chunk_repository),
                    chunk_language_writer=ChunkLanguageWriterAdapter(chunk_repository),
                    understanding_job_reader=UnderstandingJobReaderAdapter(
                        UnderstandingJobRepository(session_factory)
                    ),
                    flow_recorder=processing.flow_recorder,
                )
            return cache["services"]

    return _provider


def make_kb_acknowledge_handler(event_type: str):
    def _handle(payload: dict[str, Any]) -> None:
        logger.info(
            "%s acknowledged (item=%s job=%s)",
            event_type,
            payload.get("training_item_id"),
            payload.get("discovery_job_id") or payload.get("understanding_job_id"),
        )

    return _handle


def register_kb_event_handlers(dispatcher: Any, *, session_factory: Any = None) -> None:
    from apps.kb.kb_discovery.events.discovery_requested_handler import (
        make_discovery_requested_handler,
    )
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
    register_job_handler(
        dispatcher,
        UNDERSTANDING_COMPLETED,
        make_kb_acknowledge_handler(UNDERSTANDING_COMPLETED),
    )
    register_job_handler(
        dispatcher,
        DISCOVERY_REQUESTED,
        make_discovery_requested_handler(make_discovery_services_provider(session_factory)),
    )
    register_job_handler(dispatcher, EMBEDDING_REQUESTED, make_kb_acknowledge_handler(EMBEDDING_REQUESTED))
    register_job_handler(dispatcher, INDEXING_REQUESTED, make_kb_acknowledge_handler(INDEXING_REQUESTED))
    register_job_handler(dispatcher, DISCOVERY_COMPLETED, make_kb_acknowledge_handler(DISCOVERY_COMPLETED))
    register_job_handler(dispatcher, DISCOVERY_FAILED, make_kb_acknowledge_handler(DISCOVERY_FAILED))
    register_job_handler(
        dispatcher, UNDERSTANDING_FAILED, make_kb_acknowledge_handler(UNDERSTANDING_FAILED)
    )


__all__ = [
    "make_discovery_services_provider",
    "make_kb_acknowledge_handler",
    "make_understanding_services_provider",
    "register_kb_event_handlers",
]
