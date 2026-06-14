from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter
from apps.kb.kb_indexing.adapters.QdrantCollectionManager import QdrantCollectionManager
from apps.kb.kb_indexing.repository.IndexedChunkRepository import IndexedChunkRepository
from apps.kb.kb_indexing.repository.IndexingJobRepository import IndexingJobRepository
from apps.kb.kb_indexing.service.BuildQdrantPayloadService import BuildQdrantPayloadService
from apps.kb.kb_indexing.service.BuildQdrantPointService import BuildQdrantPointService
from apps.kb.kb_indexing.service.EnsureQdrantCollectionService import EnsureQdrantCollectionService
from apps.kb.kb_indexing.service.IndexingPipelineService import IndexingPipelineService
from apps.kb.kb_indexing.service.StartIndexingService import StartIndexingService
from apps.kb.kb_indexing.service.UpsertQdrantPointsService import UpsertQdrantPointsService
from apps.kb.kb_indexing.service.ValidateIndexingService import ValidateIndexingService
from apps.kb.shared.ports.processing_flow_recorder import NoOpProcessingFlowRecorder


@dataclass(frozen=True)
class IndexingServices:
    job_repository: IndexingJobRepository
    indexed_chunk_repository: IndexedChunkRepository
    start_service: StartIndexingService
    pipeline: IndexingPipelineService


def build_indexing_services(
    *,
    session_factory,
    chunk_reader,
    embedding_reader,
    embedding_job_reader,
    bundle_reader,
    knowledge_base_reader,
    flow_recorder=None,
    metrics_updater=None,
) -> IndexingServices:
    job_repository = IndexingJobRepository(session_factory)
    indexed_chunk_repository = IndexedChunkRepository(session_factory)
    qdrant_adapter = QdrantAdapter()
    collection_manager = QdrantCollectionManager(qdrant_adapter)
    ensure_collection = EnsureQdrantCollectionService(collection_manager)
    payload_service = BuildQdrantPayloadService()
    build_point = BuildQdrantPointService(payload_service)
    upsert = UpsertQdrantPointsService(qdrant_adapter, indexed_chunk_repository)
    validate = ValidateIndexingService(indexed_chunk_repository)
    pipeline = IndexingPipelineService(
        job_repository,
        chunk_reader,
        embedding_reader,
        bundle_reader,
        ensure_collection,
        build_point,
        upsert,
        validate,
        flow_recorder=flow_recorder or NoOpProcessingFlowRecorder(),
        metrics_updater=metrics_updater,
    )
    start_service = StartIndexingService(
        job_repository,
        embedding_job_reader,
        knowledge_base_reader,
        pipeline,
    )
    return IndexingServices(
        job_repository=job_repository,
        indexed_chunk_repository=indexed_chunk_repository,
        start_service=start_service,
        pipeline=pipeline,
    )


__all__ = ["IndexingServices", "build_indexing_services"]
