from __future__ import annotations

from dataclasses import dataclass

from apps.kb.bootstrap.embedding_indexing_wiring import KnowledgeBaseReaderAdapter
from apps.kb.kb_embedding.bootstrap.embedding_assembly import _build_embedding_provider
from apps.kb.kb_indexing.adapters.QdrantAdapter import QdrantAdapter
from apps.kb.kb_indexing.repository.IndexVerificationRepository import IndexVerificationRepository
from apps.kb.kb_indexing.repository.IndexingJobRepository import IndexingJobRepository
from apps.kb.kb_processing.repository.ProcessingMetricsRepository import ProcessingMetricsRepository
from apps.kb.kb_processing.repository.ProcessingEventRepository import ProcessingEventRepository
from apps.kb.kb_processing.repository.ProcessingIssueRepository import ProcessingIssueRepository
from apps.kb.kb_processing.service.ProcessingEventService import ProcessingEventService
from apps.kb.kb_processing.service.ProcessingIssueService import ProcessingIssueService
from apps.kb.kb_search.service.SearchIssueRecorderService import SearchIssueRecorderService
from apps.kb.kb_search.adapters.QdrantSearchAdapter import QdrantSearchAdapter
from apps.kb.kb_search.adapters.QueryEmbeddingProviderAdapter import QueryEmbeddingProviderAdapter
from apps.kb.kb_search.repository.SearchCitationRepository import SearchCitationRepository
from apps.kb.kb_search.repository.SearchContextBlockRepository import SearchContextBlockRepository
from apps.kb.kb_search.repository.SearchQueryResultRepository import SearchQueryResultRepository
from apps.kb.kb_search.repository.SearchQueryRunRepository import SearchQueryRunRepository
from apps.kb.kb_search.service.BuildCitationService import BuildCitationService
from apps.kb.kb_search.service.BuildQueryEmbeddingService import BuildQueryEmbeddingService
from apps.kb.kb_search.service.BuildSearchContextService import BuildSearchContextService
from apps.kb.kb_search.service.BuildSearchQueryService import BuildSearchQueryService
from apps.kb.kb_search.service.HybridRankService import HybridRankService
from apps.kb.kb_search.service.KbSearchChatFacade import KbSearchChatFacade
from apps.kb.kb_search.service.KbSearchPipelineService import KbSearchPipelineService
from apps.kb.kb_search.service.PostgresHydrationService import PostgresHydrationService
from apps.kb.kb_search.service.QdrantVectorSearchService import PayloadFilterService, QdrantVectorSearchService
from apps.kb.kb_search.service.SearchReadinessService import SearchReadinessService
from apps.kb.kb_search.service.StoreSearchRunService import StoreSearchRunService
from core.kernel.config.config_loader import settings


@dataclass(frozen=True)
class SearchServices:
    run_repository: SearchQueryRunRepository
    chat_facade: KbSearchChatFacade
    pipeline: KbSearchPipelineService


def build_search_services(
    *,
    session_factory,
    access_checker: object | None = None,
) -> SearchServices:
    run_repository = SearchQueryRunRepository(session_factory)
    result_repository = SearchQueryResultRepository(session_factory)
    block_repository = SearchContextBlockRepository(session_factory)
    citation_repository = SearchCitationRepository(session_factory)
    kb_reader = KnowledgeBaseReaderAdapter(session_factory)
    qdrant_search = QdrantSearchAdapter(QdrantAdapter())

    dimension = int(settings.embedding_vector_size or 1024)
    batch_size = int(settings.embedding_batch_size or 16)
    provider, _, _ = _build_embedding_provider(
        str(settings.embedding_provider or "local"),
        dimension,
        batch_size,
    )
    query_embedding = QueryEmbeddingProviderAdapter(provider, default_dimension=dimension)

    readiness = SearchReadinessService(
        metrics_repository=ProcessingMetricsRepository(session_factory),
        indexing_job_repository=IndexingJobRepository(session_factory),
        verification_repository=IndexVerificationRepository(session_factory),
        qdrant_search=qdrant_search,
        knowledge_base_reader=kb_reader,
    )
    payload_filter = PayloadFilterService()
    vector_search = QdrantVectorSearchService(
        qdrant_search=qdrant_search,
        payload_filter_service=payload_filter,
        knowledge_base_reader=kb_reader,
    )
    store_run = StoreSearchRunService(
        run_repository=run_repository,
        result_repository=result_repository,
        context_block_repository=block_repository,
        citation_repository=citation_repository,
    )
    issue_repository = ProcessingIssueRepository(session_factory)
    event_repository = ProcessingEventRepository(session_factory)
    issue_recorder = SearchIssueRecorderService(
        issue_service=ProcessingIssueService(issue_repository),
        event_service=ProcessingEventService(event_repository),
    )
    pipeline = KbSearchPipelineService(
        run_repository=run_repository,
        readiness_service=readiness,
        build_query_service=BuildSearchQueryService(),
        build_embedding_service=BuildQueryEmbeddingService(
            session_factory=session_factory,
            query_embedding_adapter=query_embedding,
        ),
        vector_search_service=vector_search,
        hybrid_rank_service=HybridRankService(),
        hydration_service=PostgresHydrationService(session_factory),
        build_context_service=BuildSearchContextService(),
        build_citation_service=BuildCitationService(),
        store_run_service=store_run,
        knowledge_base_reader=kb_reader,
        issue_recorder=issue_recorder,
        default_top_k=int(getattr(settings, "kb_search_top_k", 10) or 10),
    )
    chat_facade = KbSearchChatFacade(
        pipeline=pipeline,
        run_repository=run_repository,
        result_repository=result_repository,
        context_block_repository=block_repository,
        citation_repository=citation_repository,
        access_checker=access_checker,
    )
    return SearchServices(
        run_repository=run_repository,
        chat_facade=chat_facade,
        pipeline=pipeline,
    )


__all__ = ["SearchServices", "build_search_services"]
