# Ez a fájl egy modul regisztrációját, wiringját és publikus integrációját tartalmazza.
from __future__ import annotations

from dataclasses import dataclass

from core.kernel.config.config_loader import settings
from apps.knowledge.ai.embedding_provider import EmbeddingProvider, build_embedding_provider_from_settings
from apps.knowledge.ai.embedding_service import EmbeddingService
from apps.knowledge.qdrant.qdrant_wrapper import QdrantClientWrapper
from apps.knowledge.repositories.knowledge_base_repository import MySQLKnowledgeBaseRepository
from apps.knowledge.repositories.knowledge_runtime_repository import (
    SQLAlchemyIndexBuildStore,
    SQLAlchemyQueryRunStore,
    SQLAlchemySourceStore,
)
from apps.knowledge.repositories.knowledge_ingest_repository import (
    SQLAlchemyIngestEventStore,
    SQLAlchemyIngestInputStore,
    SQLAlchemyIngestItemStore,
    SQLAlchemyIngestRunStore,
)
from apps.knowledge.repositories.knowledge_interpretation_repository import (
    SQLAlchemyClaimStore,
    SQLAlchemyInterpretationRunStore,
    SQLAlchemyMentionStore,
    SQLAlchemySentenceInterpretationStore,
    SQLAlchemySpaceTimeFrameStore,
)
from apps.knowledge.repository.local_entity_cluster_repository import LocalEntityClusterRepository
from apps.knowledge.repositories.knowledge_parser_repository import (
    SQLAlchemyDocumentStore,
    SQLAlchemyParagraphStore,
    SQLAlchemyParserRunStore,
    SQLAlchemySentenceStore,
)
from apps.knowledge.service.claim_split import build_default_claim_fine_splitter
from apps.knowledge.service.knowledge_facade import KnowledgeFacade
from apps.knowledge.service.runtime_store import (
    InMemoryIndexProfileStore,
    InMemoryMetricsStore,
    SimpleChunkBuilder,
    SimpleContextBuilder,
    SimpleRetrievalEngine,
)
from shared.object_storage import get_object_storage


@dataclass(frozen=True)
class KnowledgeModuleInfrastructure:
    db_session_factory: object
    user_repository: object
    source_store: SQLAlchemySourceStore
    ingest_run_store: SQLAlchemyIngestRunStore
    ingest_item_store: SQLAlchemyIngestItemStore
    ingest_input_store: SQLAlchemyIngestInputStore
    ingest_event_store: SQLAlchemyIngestEventStore
    parser_run_store: SQLAlchemyParserRunStore
    document_store: SQLAlchemyDocumentStore
    paragraph_store: SQLAlchemyParagraphStore
    sentence_store: SQLAlchemySentenceStore
    interpretation_run_store: SQLAlchemyInterpretationRunStore
    sentence_interpretation_store: SQLAlchemySentenceInterpretationStore
    mention_store: SQLAlchemyMentionStore
    claim_store: SQLAlchemyClaimStore
    space_time_frame_store: SQLAlchemySpaceTimeFrameStore
    index_profile_store: InMemoryIndexProfileStore
    index_build_store: SQLAlchemyIndexBuildStore
    query_run_store: SQLAlchemyQueryRunStore
    metrics_store: InMemoryMetricsStore

    # Ez a metódus felépíti a(z) repository logikáját.
    def build_repository(self) -> MySQLKnowledgeBaseRepository:
        return MySQLKnowledgeBaseRepository(self.db_session_factory)

    # Ez a metódus felépíti a(z) embedding szolgáltatás logikáját.
    def build_embedding_service(self) -> EmbeddingService:
        return EmbeddingService(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
            vector_size=settings.embedding_vector_size,
        )

    def build_embedding_provider(self) -> EmbeddingProvider:
        return build_embedding_provider_from_settings(settings)

    # Ez a metódus felépíti a(z) Qdrant client logikáját.
    def build_qdrant_client(self) -> QdrantClientWrapper:
        return QdrantClientWrapper(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            embedding_provider=self.build_embedding_provider(),
            timeout=settings.qdrant_timeout_sec,
        )

    # Ez a metódus felépíti a(z) szolgáltatás logikáját.
    def build_service(self, repo: MySQLKnowledgeBaseRepository) -> KnowledgeFacade:
        return KnowledgeFacade(
            corpus_store=repo,
            user_repo=self.user_repository,
            source_store=self.source_store,
            ingest_run_store=self.ingest_run_store,
            ingest_item_store=self.ingest_item_store,
            ingest_input_store=self.ingest_input_store,
            ingest_event_store=self.ingest_event_store,
            parser_run_store=self.parser_run_store,
            document_store=self.document_store,
            paragraph_store=self.paragraph_store,
            sentence_store=self.sentence_store,
            interpretation_run_store=self.interpretation_run_store,
            sentence_interpretation_store=self.sentence_interpretation_store,
            mention_store=self.mention_store,
            claim_store=self.claim_store,
            space_time_frame_store=self.space_time_frame_store,
            local_entity_cluster_repository=LocalEntityClusterRepository(self.db_session_factory),
            index_profile_store=self.index_profile_store,
            index_build_store=self.index_build_store,
            query_run_store=self.query_run_store,
            chunk_builder=SimpleChunkBuilder(),
            retrieval_engine=SimpleRetrievalEngine(self.build_qdrant_client),
            context_builder=SimpleContextBuilder(),
            vector_index_factory=self.build_qdrant_client,
            metrics_store=self.metrics_store,
            object_storage=get_object_storage(),
            claim_fine_splitter=build_default_claim_fine_splitter(),
        )


# Ez a függvény felépíti a(z) knowledge infrastructure logikáját.
def build_knowledge_infrastructure(*, db_session_factory: object, user_repository: object) -> KnowledgeModuleInfrastructure:
    return KnowledgeModuleInfrastructure(
        db_session_factory=db_session_factory,
        user_repository=user_repository,
        source_store=SQLAlchemySourceStore(db_session_factory),
        ingest_run_store=SQLAlchemyIngestRunStore(db_session_factory),
        ingest_item_store=SQLAlchemyIngestItemStore(db_session_factory),
        ingest_input_store=SQLAlchemyIngestInputStore(db_session_factory),
        ingest_event_store=SQLAlchemyIngestEventStore(db_session_factory),
        parser_run_store=SQLAlchemyParserRunStore(db_session_factory),
        document_store=SQLAlchemyDocumentStore(db_session_factory),
        paragraph_store=SQLAlchemyParagraphStore(db_session_factory),
        sentence_store=SQLAlchemySentenceStore(db_session_factory),
        interpretation_run_store=SQLAlchemyInterpretationRunStore(db_session_factory),
        sentence_interpretation_store=SQLAlchemySentenceInterpretationStore(db_session_factory),
        mention_store=SQLAlchemyMentionStore(db_session_factory),
        claim_store=SQLAlchemyClaimStore(db_session_factory),
        space_time_frame_store=SQLAlchemySpaceTimeFrameStore(db_session_factory),
        index_profile_store=InMemoryIndexProfileStore(),
        index_build_store=SQLAlchemyIndexBuildStore(db_session_factory),
        query_run_store=SQLAlchemyQueryRunStore(db_session_factory),
        metrics_store=InMemoryMetricsStore(),
    )
