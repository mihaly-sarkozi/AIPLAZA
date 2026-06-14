from __future__ import annotations

import logging
import threading
from typing import Any

"""
KB cross-module event wiring (canonical hely).

Az összes KB pipeline event handler regisztrációja itt történik:
  understanding → discovery → embedding → indexing

Modulok `register_event_handlers()` metódusa szándékos no-op / deprecated;
ne regisztráljanak duplikált handlert lokálisan.
"""

from core.kernel.jobs import register_job_handler

from apps.kb.shared.events import (
    DISCOVERY_COMPLETED,
    DISCOVERY_FAILED,
    DISCOVERY_REQUESTED,
    EMBEDDING_REQUESTED,
    INDEXING_COMPLETED,
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


def make_embedding_services_provider(session_factory: Any):
    lock = threading.Lock()
    cache: dict[str, Any] = {}

    def _provider():
        if session_factory is None:
            raise RuntimeError("kb embedding handler: hiányzó session_factory")
        with lock:
            if "services" not in cache:
                from apps.kb.bootstrap.discovery_wiring import UnderstandingJobReaderAdapter
                from apps.kb.bootstrap.embedding_indexing_wiring import (
                    DiscoveryJobReaderAdapter,
                    EmbeddingChunkReaderAdapter,
                    EmbeddingDiscoveryBundleReaderAdapter,
                )
                from apps.kb.kb_discovery.repository.DiscoveryBundleRepository import DiscoveryBundleRepository
                from apps.kb.kb_discovery.repository.DiscoveryJobRepository import DiscoveryJobRepository
                from apps.kb.kb_discovery.repository.EnrichmentRepository import EnrichmentRepository
                from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository
                from apps.kb.kb_discovery.repository.ProcessRepository import ProcessRepository
                from apps.kb.kb_discovery.repository.RelationshipRepository import RelationshipRepository
                from apps.kb.kb_discovery.repository.ScoreRepository import ScoreRepository
                from apps.kb.kb_discovery.repository.SpatialRepository import SpatialRepository
                from apps.kb.kb_discovery.repository.TemporalRepository import TemporalRepository
                from apps.kb.kb_embedding.bootstrap.embedding_assembly import build_embedding_services
                from apps.kb.kb_processing.bootstrap.processing_assembly import build_processing_services
                from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
                from apps.kb.kb_understanding.repository.UnderstandingJobRepository import UnderstandingJobRepository

                chunk_repository = ChunkRepository(session_factory)
                processing = build_processing_services(session_factory=session_factory)
                understanding_job_reader = UnderstandingJobReaderAdapter(
                    UnderstandingJobRepository(session_factory)
                )
                discovery_job_repository = DiscoveryJobRepository(session_factory)
                bundle_repository = DiscoveryBundleRepository(
                    EnrichmentRepository(session_factory),
                    EntityRepository(session_factory),
                    EntityMentionRepository(session_factory),
                    TemporalRepository(session_factory),
                    SpatialRepository(session_factory),
                    ProcessRepository(session_factory),
                    RelationshipRepository(session_factory),
                    ScoreRepository(session_factory),
                )
                cache["services"] = build_embedding_services(
                    session_factory=session_factory,
                    chunk_reader=EmbeddingChunkReaderAdapter(chunk_repository),
                    discovery_job_reader=DiscoveryJobReaderAdapter(
                        discovery_job_repository,
                        understanding_job_reader=understanding_job_reader,
                    ),
                    bundle_reader=EmbeddingDiscoveryBundleReaderAdapter(bundle_repository),
                    flow_recorder=processing.flow_recorder,
                )
            return cache["services"]

    return _provider


def make_indexing_services_provider(session_factory: Any):
    lock = threading.Lock()
    cache: dict[str, Any] = {}

    def _provider():
        if session_factory is None:
            raise RuntimeError("kb indexing handler: hiányzó session_factory")
        with lock:
            if "services" not in cache:
                from apps.kb.bootstrap.discovery_wiring import UnderstandingJobReaderAdapter
                from apps.kb.bootstrap.embedding_indexing_wiring import (
                    DiscoveryJobReaderAdapter,
                    EmbeddingJobReaderAdapter,
                    EmbeddingRecordReaderAdapter,
                    IndexingChunkReaderAdapter,
                    IndexingDiscoveryBundleReaderAdapter,
                    KnowledgeBaseReaderAdapter,
                )
                from apps.kb.kb_discovery.repository.DiscoveryBundleRepository import DiscoveryBundleRepository
                from apps.kb.kb_discovery.repository.DiscoveryJobRepository import DiscoveryJobRepository
                from apps.kb.kb_discovery.repository.EnrichmentRepository import EnrichmentRepository
                from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository
                from apps.kb.kb_discovery.repository.ProcessRepository import ProcessRepository
                from apps.kb.kb_discovery.repository.RelationshipRepository import RelationshipRepository
                from apps.kb.kb_discovery.repository.ScoreRepository import ScoreRepository
                from apps.kb.kb_discovery.repository.SpatialRepository import SpatialRepository
                from apps.kb.kb_discovery.repository.TemporalRepository import TemporalRepository
                from apps.kb.kb_embedding.repository.EmbeddingJobRepository import EmbeddingJobRepository
                from apps.kb.kb_embedding.repository.KnowledgeEmbeddingRepository import KnowledgeEmbeddingRepository
                from apps.kb.kb_indexing.bootstrap.indexing_assembly import build_indexing_services
                from apps.kb.kb_processing.bootstrap.processing_assembly import build_processing_services
                from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
                from apps.kb.kb_understanding.repository.UnderstandingJobRepository import UnderstandingJobRepository

                chunk_repository = ChunkRepository(session_factory)
                processing = build_processing_services(session_factory=session_factory)
                understanding_job_reader = UnderstandingJobReaderAdapter(
                    UnderstandingJobRepository(session_factory)
                )
                discovery_job_repository = DiscoveryJobRepository(session_factory)
                discovery_job_reader = DiscoveryJobReaderAdapter(
                    discovery_job_repository,
                    understanding_job_reader=understanding_job_reader,
                )
                bundle_repository = DiscoveryBundleRepository(
                    EnrichmentRepository(session_factory),
                    EntityRepository(session_factory),
                    EntityMentionRepository(session_factory),
                    TemporalRepository(session_factory),
                    SpatialRepository(session_factory),
                    ProcessRepository(session_factory),
                    RelationshipRepository(session_factory),
                    ScoreRepository(session_factory),
                )
                embedding_job_repository = EmbeddingJobRepository(session_factory)
                embedding_repository = KnowledgeEmbeddingRepository(session_factory)
                cache["services"] = build_indexing_services(
                    session_factory=session_factory,
                    chunk_reader=IndexingChunkReaderAdapter(chunk_repository),
                    embedding_reader=EmbeddingRecordReaderAdapter(embedding_repository),
                    embedding_job_reader=EmbeddingJobReaderAdapter(
                        embedding_job_repository,
                        discovery_job_reader,
                    ),
                    bundle_reader=IndexingDiscoveryBundleReaderAdapter(
                        bundle_repository,
                        chunk_repository,
                    ),
                    knowledge_base_reader=KnowledgeBaseReaderAdapter(session_factory),
                    flow_recorder=processing.flow_recorder,
                    metrics_updater=lambda kb_id, tenant_slug: processing.metrics_service.update_after_indexing(
                        kb_id,
                        tenant_slug=tenant_slug,
                    ),
                    metrics_repository=processing.metrics_repository,
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
    from apps.kb.kb_embedding.events.embedding_requested_handler import (
        make_embedding_requested_handler,
    )
    from apps.kb.kb_indexing.events.indexing_requested_handler import (
        make_indexing_requested_handler,
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
    register_job_handler(
        dispatcher,
        EMBEDDING_REQUESTED,
        make_embedding_requested_handler(make_embedding_services_provider(session_factory)),
    )
    register_job_handler(
        dispatcher,
        INDEXING_REQUESTED,
        make_indexing_requested_handler(make_indexing_services_provider(session_factory)),
    )
    register_job_handler(dispatcher, INDEXING_COMPLETED, make_kb_acknowledge_handler(INDEXING_COMPLETED))
    register_job_handler(dispatcher, DISCOVERY_COMPLETED, make_kb_acknowledge_handler(DISCOVERY_COMPLETED))
    register_job_handler(dispatcher, DISCOVERY_FAILED, make_kb_acknowledge_handler(DISCOVERY_FAILED))
    register_job_handler(
        dispatcher, UNDERSTANDING_FAILED, make_kb_acknowledge_handler(UNDERSTANDING_FAILED)
    )


__all__ = [
    "make_discovery_services_provider",
    "make_embedding_services_provider",
    "make_indexing_services_provider",
    "make_kb_acknowledge_handler",
    "make_understanding_services_provider",
    "register_kb_event_handlers",
]
