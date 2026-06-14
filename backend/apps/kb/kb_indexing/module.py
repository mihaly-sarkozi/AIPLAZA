from __future__ import annotations


class KbIndexingModule:
    name = "kb.indexing"

    def register_routes(self, app) -> None:
        from .router import router

        app.include_router(router)

    def register_services(self, container) -> None:
        from apps.kb.kb_indexing.bootstrap.indexing_assembly import build_indexing_services
        from apps.kb.kb_indexing.bootstrap.service_keys import (
            KB_INDEXED_CHUNK_REPOSITORY,
            KB_INDEXING_DIAGNOSTICS_SERVICE,
            KB_INDEXING_JOB_REPOSITORY,
        )
        from apps.kb.kb_processing.bootstrap.processing_assembly import build_processing_services
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
        from apps.kb.bootstrap.discovery_wiring import UnderstandingJobReaderAdapter
        from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
        from apps.kb.kb_understanding.repository.UnderstandingJobRepository import UnderstandingJobRepository

        sf = container.session_factory
        processing = build_processing_services(session_factory=sf)
        chunk_repository = ChunkRepository(sf)
        understanding_job_reader = UnderstandingJobReaderAdapter(UnderstandingJobRepository(sf))
        discovery_job_reader = DiscoveryJobReaderAdapter(
            DiscoveryJobRepository(sf),
            understanding_job_reader=understanding_job_reader,
        )
        bundle_repository = DiscoveryBundleRepository(
            EnrichmentRepository(sf),
            EntityRepository(sf),
            EntityMentionRepository(sf),
            TemporalRepository(sf),
            SpatialRepository(sf),
            ProcessRepository(sf),
            RelationshipRepository(sf),
            ScoreRepository(sf),
        )
        services = build_indexing_services(
            session_factory=sf,
            chunk_reader=IndexingChunkReaderAdapter(chunk_repository),
            embedding_reader=EmbeddingRecordReaderAdapter(KnowledgeEmbeddingRepository(sf)),
            embedding_job_reader=EmbeddingJobReaderAdapter(
                EmbeddingJobRepository(sf),
                discovery_job_reader,
            ),
            bundle_reader=IndexingDiscoveryBundleReaderAdapter(bundle_repository, chunk_repository),
            knowledge_base_reader=KnowledgeBaseReaderAdapter(sf),
            flow_recorder=processing.flow_recorder,
            metrics_updater=lambda kb_id, tenant_slug: processing.metrics_service.update_after_indexing(
                kb_id,
                tenant_slug=tenant_slug,
            ),
            metrics_repository=processing.metrics_repository,
        )
        container.register_repository(KB_INDEXING_JOB_REPOSITORY, services.job_repository)
        container.register_repository(KB_INDEXED_CHUNK_REPOSITORY, services.indexed_chunk_repository)
        container.register_service(KB_INDEXING_DIAGNOSTICS_SERVICE, services.diagnostics_service)

    def register_event_handlers(self, event_bus) -> None:
        # Event handlers: apps/kb/events.py (canonical wiring)
        pass


__all__ = ["KbIndexingModule"]
