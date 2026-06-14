from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter
from apps.kb.kb_indexing.adapters.QdrantCollectionManager import QdrantCollectionManager
from apps.kb.kb_indexing.repository.IndexRebuildRepository import IndexRebuildRepository
from apps.kb.kb_indexing.repository.IndexVerificationItemRepository import IndexVerificationItemRepository
from apps.kb.kb_indexing.repository.IndexVerificationRepository import IndexVerificationRepository
from apps.kb.kb_indexing.repository.IndexedChunkRepository import IndexedChunkRepository
from apps.kb.kb_indexing.repository.IndexingJobRepository import IndexingJobRepository
from apps.kb.kb_indexing.service.BuildQdrantPayloadService import BuildQdrantPayloadService
from apps.kb.kb_indexing.service.BuildQdrantPointService import BuildQdrantPointService
from apps.kb.kb_indexing.service.DeleteIndexedChunksService import DeleteIndexedChunksService
from apps.kb.kb_indexing.service.EnsureQdrantCollectionService import EnsureQdrantCollectionService
from apps.kb.kb_indexing.service.IndexingDiagnosticsService import IndexingDiagnosticsService
from apps.kb.kb_indexing.service.IndexingFailureRecorderService import IndexingFailureRecorderService
from apps.kb.kb_indexing.service.IndexingPipelineService import IndexingPipelineService
from apps.kb.kb_indexing.service.MarkReadyForSearchService import MarkReadyForSearchService
from apps.kb.kb_indexing.service.RebuildKnowledgeBaseIndexService import RebuildKnowledgeBaseIndexService
from apps.kb.kb_indexing.service.ReindexTrainingItemService import ReindexTrainingItemService
from apps.kb.kb_indexing.service.StartIndexingService import StartIndexingService
from apps.kb.kb_indexing.service.UpsertQdrantPointsService import UpsertQdrantPointsService
from apps.kb.kb_indexing.service.ValidateIndexingService import ValidateIndexingService
from apps.kb.kb_indexing.service.VerifyQdrantStorageService import VerifyQdrantStorageService
from apps.kb.kb_processing.repository.ProcessingMetricsRepository import ProcessingMetricsRepository
from apps.kb.shared.ports.processing_flow_recorder import NoOpProcessingFlowRecorder


@dataclass(frozen=True)
class IndexingServices:
    job_repository: IndexingJobRepository
    indexed_chunk_repository: IndexedChunkRepository
    verification_repository: IndexVerificationRepository
    verification_item_repository: IndexVerificationItemRepository
    rebuild_repository: IndexRebuildRepository
    start_service: StartIndexingService
    pipeline: IndexingPipelineService
    diagnostics_service: IndexingDiagnosticsService
    delete_indexed_chunks_service: DeleteIndexedChunksService
    reindex_training_item_service: ReindexTrainingItemService
    rebuild_kb_index_service: RebuildKnowledgeBaseIndexService
    failure_recorder: IndexingFailureRecorderService


def build_indexing_services(
    *,
    session_factory,
    chunk_reader,
    embedding_reader,
    embedding_job_reader,
    bundle_reader,
    knowledge_base_reader,
    embedding_job_repository=None,
    flow_recorder=None,
    metrics_updater=None,
    metrics_repository: ProcessingMetricsRepository | None = None,
) -> IndexingServices:
    job_repository = IndexingJobRepository(session_factory)
    indexed_chunk_repository = IndexedChunkRepository(session_factory)
    verification_repository = IndexVerificationRepository(session_factory)
    verification_item_repository = IndexVerificationItemRepository(session_factory)
    rebuild_repository = IndexRebuildRepository(session_factory)
    metrics_repo = metrics_repository or ProcessingMetricsRepository(session_factory)
    recorder = flow_recorder or NoOpProcessingFlowRecorder()

    failure_recorder = IndexingFailureRecorderService(
        job_repository,
        knowledge_base_reader,
        flow_recorder=recorder,
    )

    qdrant_adapter = QdrantAdapter()
    collection_manager = QdrantCollectionManager(qdrant_adapter)
    ensure_collection = EnsureQdrantCollectionService(collection_manager)
    payload_service = BuildQdrantPayloadService()
    build_point = BuildQdrantPointService(payload_service)
    upsert = UpsertQdrantPointsService(qdrant_adapter, indexed_chunk_repository)
    validate = ValidateIndexingService(indexed_chunk_repository)
    verify = VerifyQdrantStorageService(
        qdrant_adapter,
        indexed_chunk_repository,
        verification_repository,
        verification_item_repository,
        flow_recorder=recorder,
    )
    mark_ready = MarkReadyForSearchService(
        job_repository,
        embedding_job_reader,
        metrics_repo,
        flow_recorder=recorder,
    )
    pipeline = IndexingPipelineService(
        job_repository,
        chunk_reader,
        embedding_reader,
        bundle_reader,
        ensure_collection,
        build_point,
        upsert,
        validate,
        verify,
        mark_ready,
        flow_recorder=recorder,
        metrics_updater=metrics_updater,
    )
    start_service = StartIndexingService(
        job_repository,
        embedding_job_reader,
        knowledge_base_reader,
        pipeline,
        failure_recorder,
    )
    diagnostics = IndexingDiagnosticsService(
        session_factory=session_factory,
        indexing_job_repository=job_repository,
        indexed_chunk_repository=indexed_chunk_repository,
        verification_repository=verification_repository,
        embedding_job_reader=embedding_job_reader,
        knowledge_base_reader=knowledge_base_reader,
        metrics_repository=metrics_repo,
        qdrant_adapter=qdrant_adapter,
    )
    delete_service = DeleteIndexedChunksService(qdrant_adapter, indexed_chunk_repository)

    from apps.kb.kb_embedding.repository.EmbeddingJobRepository import EmbeddingJobRepository

    emb_repo = embedding_job_repository or EmbeddingJobRepository(session_factory)
    reindex_service = ReindexTrainingItemService(
        embedding_job_repository=emb_repo,
        indexing_job_repository=job_repository,
        verification_repository=verification_repository,
        knowledge_base_reader=knowledge_base_reader,
        delete_service=delete_service,
        start_indexing_service=start_service,
        failure_recorder=failure_recorder,
        flow_recorder=recorder,
    )
    rebuild_service = RebuildKnowledgeBaseIndexService(
        rebuild_repository=rebuild_repository,
        embedding_job_repository=emb_repo,
        knowledge_base_reader=knowledge_base_reader,
        delete_service=delete_service,
        reindex_service=reindex_service,
        metrics_repository=metrics_repo,
        flow_recorder=recorder,
    )

    return IndexingServices(
        job_repository=job_repository,
        indexed_chunk_repository=indexed_chunk_repository,
        verification_repository=verification_repository,
        verification_item_repository=verification_item_repository,
        rebuild_repository=rebuild_repository,
        start_service=start_service,
        pipeline=pipeline,
        diagnostics_service=diagnostics,
        delete_indexed_chunks_service=delete_service,
        reindex_training_item_service=reindex_service,
        rebuild_kb_index_service=rebuild_service,
        failure_recorder=failure_recorder,
    )


__all__ = ["IndexingServices", "build_indexing_services"]
