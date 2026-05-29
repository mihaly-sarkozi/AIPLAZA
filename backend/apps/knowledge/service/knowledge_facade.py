from __future__ import annotations

import asyncio

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403
from apps.knowledge.service.facade_internal_api import InternalFacadeMixin
from apps.knowledge.service.facade_sentence_compat import SentenceCompatibilityMixin
from apps.knowledge.service.facade_claim_support import ClaimInterpretationSupportMixin
from apps.knowledge.service.facade_local_entity_support import LocalEntitySupportMixin
from apps.knowledge.service.facade_corpus_api import CorpusFacadeMixin
from apps.knowledge.service.facade_source_api import SourceFacadeMixin
from apps.knowledge.service.facade_ingest_api import IngestFacadeMixin
from apps.knowledge.service.facade_interpretation_api import InterpretationFacadeMixin
from apps.knowledge.service.facade_index_api import IndexFacadeMixin
from apps.knowledge.service.facade_feedback_api import FeedbackFacadeMixin
from apps.knowledge.service.facade_retrieval_api import RetrievalFacadeMixin
from apps.knowledge.service.facade_progress_compat import ProgressCompatibilityMixin
from apps.knowledge.service.knowledge_facade_factory import build_knowledge_facade_from_init

class KnowledgeFacade(
    InternalFacadeMixin,
    ProgressCompatibilityMixin,
    SentenceCompatibilityMixin,
    ClaimInterpretationSupportMixin,
    LocalEntitySupportMixin,
    CorpusFacadeMixin,
    SourceFacadeMixin,
    IngestFacadeMixin,
    InterpretationFacadeMixin,
    IndexFacadeMixin,
    FeedbackFacadeMixin,
    RetrievalFacadeMixin,
):
    _PARSER_ERROR_MESSAGE_MAX = 1000
    _INTERPRETATION_ERROR_MESSAGE_MAX = 480
    _STALE_PARSER_RESTART_AFTER_SEC = 120
    _STALE_INGEST_RUN_FAIL_AFTER_SEC = 900
    _STALE_INDEX_BUILD_FAIL_AFTER_SEC = 1200
    _ENABLE_CLAIM_FINE_SPLIT_DURING_PARSING = True
    _CLAIM_FINE_SPLIT_EARLY_STOP_AFTER_BLOCKS = 24
    _CLAIM_FINE_SPLIT_MIN_HIT_BLOCKS_TO_CONTINUE = 2
    _INDEX_BUILD_RETRY_COUNT = 2
    _INDEX_BUILD_RETRY_BACKOFF_SEC = 2.0

    def __init__(
        self,
        *,
        corpus_store: CorpusStorePort,
        user_repo: Any = None,
        source_store: SourceStorePort,
        ingest_run_store: IngestRunStorePort,
        ingest_item_store: IngestItemStorePort,
        ingest_input_store: IngestInputStorePort,
        ingest_event_store: IngestEventStorePort,
        parser_run_store: ParserRunStorePort,
        document_store: DocumentStorePort,
        paragraph_store: ParagraphStorePort,
        sentence_store: SentenceStorePort,
        interpretation_run_store: InterpretationRunStorePort | None = None,
        sentence_interpretation_store: SentenceInterpretationStorePort | None = None,
        mention_store: MentionStorePort | None = None,
        claim_store: ClaimStorePort | None = None,
        space_time_frame_store: SpaceTimeFrameStorePort | None = None,
        local_entity_cluster_repository: Any | None = None,
        claim_fine_splitter: ClaimFineSplitter | None = None,
        index_profile_store: IndexProfileStorePort,
        index_build_store: IndexBuildStorePort,
        query_run_store: QueryRunStorePort,
        chunk_builder: ChunkBuilderPort,
        retrieval_engine: RetrievalEnginePort,
        context_builder: ContextBuilderPort,
        vector_index_factory: VectorIndexFactory,
        metrics_store: MetricsStorePort,
        object_storage: ObjectStoragePort,
        source_storage_service: SourceStorageService | None = None,
        audit_service: Any | None = None,
    ) -> None:
        self._runtime = build_knowledge_facade_from_init(self, locals())


__all__ = ["KnowledgeFacade"]
