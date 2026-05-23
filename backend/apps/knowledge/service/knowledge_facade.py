from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
import re
import time
import threading
import uuid as uuid_lib
from dataclasses import replace
from datetime import datetime
from typing import Any

from apps.knowledge.domain.context_profile import ContextProfile
from apps.knowledge.domain.claim import Claim
from apps.knowledge.domain.corpus import Corpus
from apps.knowledge.domain.document import Document
from apps.knowledge.domain.ingest_event import IngestEvent
from apps.knowledge.domain.ingest_input import IngestInput
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.domain.local_entity_cluster import LocalEntityCluster
from apps.knowledge.domain.index_build import IndexBuild
from apps.knowledge.domain.index_profile import DEFAULT_INDEX_PROFILE, IndexProfile
from apps.knowledge.domain.interpretation_run import InterpretationRun
from apps.knowledge.domain.mention import Mention
from apps.knowledge.domain.paragraph import Paragraph
from apps.knowledge.domain.parser_run import ParserRun
from apps.knowledge.domain.query_run import QueryRun
from apps.knowledge.domain.retrieval_profile import RetrievalProfile
from apps.knowledge.domain.sentence import Sentence
from apps.knowledge.domain.sentence_interpretation import SentenceInterpretation
from apps.knowledge.domain.source import Source
from apps.knowledge.domain.space_time_frame import SpaceTimeFrame
from apps.knowledge.service.facade_helpers import (
    SentenceCandidate,
    aggregate_ingest_item_quality as _aggregate_ingest_item_quality,
    is_uuid_string as _is_uuid_string,
    search_profile_from_trace_payload as _search_profile_from_trace_payload,
    truncate_diagnostic_text as _truncate_diagnostic_text,
    utcnow as _utcnow,
)
from apps.knowledge.service.claim_split import ClaimFineSplitter
from apps.knowledge.service.claim_extractor_v1 import ClaimExtractorV1
from apps.knowledge.service.claim_payload_builder import ClaimPayloadBuilder
from apps.knowledge.service.claim_quality_gate import ClaimQualityGate
from apps.knowledge.service.chunking_service import ChunkingService
from apps.knowledge.service.knowledge_audit_service import KnowledgeAuditService
from apps.knowledge.service.knowledge_permission_service import KnowledgePermissionService
from apps.knowledge.service.knowledge_trace_service import KnowledgeTraceService
from apps.knowledge.service.language_rules import detect_language, resolve_language
from apps.knowledge.service.mention_extractor import MentionExtractor, debug_print as debug_print_mentions
from apps.knowledge.service.local_resolver_v1 import LocalResolverV1
from apps.knowledge.service.semantic_block_selection import (
    filter_relevant_semantic_blocks,
    is_broad_function_query,
    order_chunks_by_vector_hits,
    query_phrase_for_blocks,
    query_terms_for_blocks,
    retrieval_chunks_from_vector_hits,
    select_semantic_blocks_for_query,
    semantic_block_search_text,
    semantic_blocks_context,
    semantic_blocks_from_vector_hits,
)
from apps.knowledge.service.space_time_extractor_v1 import SpaceTimeExtractorV1
from apps.knowledge.service.url_fetch_service import UrlFetchService
from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.document_interpretation_service import DocumentInterpretationService
from apps.knowledge.service.retrieval_chunk_index_v0 import build_retrieval_chunk_index_rows
from apps.knowledge.service.semantic_block_index_v0 import build_semantic_block_index_rows
from apps.knowledge.service.semantic_block_quality_v0 import enrich_semantic_blocks_with_quality
from apps.knowledge.service.knowledge_feedback_service import KnowledgeFeedbackService
from apps.knowledge.service.knowledge_lineage_service import KnowledgeLineageService
from apps.knowledge.service.knowledge_report_service import KnowledgeReportService
from apps.knowledge.service.knowledge_cleanup_service import KnowledgeCleanupService
from apps.knowledge.service.knowledge_pii_service import KnowledgePiiService
from apps.knowledge.service.ingest_progress_service import IngestProgressService
from apps.knowledge.service.ingest_run_creation_service import IngestRunCreationService
from apps.knowledge.service.ingest_run_service import IngestRunService
from apps.knowledge.service.index_build_service import IndexBuildService
from apps.knowledge.service.ingest_item_processor import IngestItemProcessor
from apps.knowledge.service.ingest_run_processor import IngestRunProcessor
from apps.knowledge.service.information_value_scorer import InformationValueScorer
from apps.knowledge.service.mention_resolution_service import MentionResolutionService
from apps.knowledge.service.parser_orchestrator import ParserOrchestrator
from apps.knowledge.service.source_storage_service import SourceStorageService
from apps.knowledge.service.source_access_service import SourceAccessService
from apps.knowledge.service.retrieval_service import RetrievalService
from apps.knowledge.service.sentence_unit_builder import SentenceUnitBuilder
from apps.knowledge.service.ports import (
    ClaimStorePort,
    ChunkBuilderPort,
    ContextBuilderPort,
    CorpusStorePort,
    DocumentStorePort,
    IngestEventStorePort,
    IngestInputStorePort,
    IngestItemStorePort,
    IngestRunStorePort,
    IndexBuildStorePort,
    IndexProfileStorePort,
    InterpretationRunStorePort,
    MentionStorePort,
    MetricsStorePort,
    ParagraphStorePort,
    ParserRunStorePort,
    QueryRunStorePort,
    RetrievalEnginePort,
    SpaceTimeFrameStorePort,
    SentenceInterpretationStorePort,
    SentenceStorePort,
    SourceStorePort,
    VectorIndexFactory,
)
from apps.knowledge.training_ingest import build_sentence_rows
from core.modules.users.domain.dto import User
from core.kernel.interface.observability import (
    increment_metric as increment_platform_metric,
    observability_scope,
)
from core.kernel.config.config_loader import settings
from shared.documents import ExtractedDocument, ExtractedParagraph, extract_document_from_upload, extract_text_from_upload
from shared.object_storage.contracts import ObjectStoragePort
from sqlalchemy.exc import ProgrammingError

logger = logging.getLogger(__name__)

class KnowledgeFacade:
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
    ) -> None:
        self._corpus_store = corpus_store
        self._user_repo = user_repo
        self._source_store = source_store
        self._ingest_run_store = ingest_run_store
        self._ingest_item_store = ingest_item_store
        self._ingest_input_store = ingest_input_store
        self._ingest_event_store = ingest_event_store
        self._parser_run_store = parser_run_store
        self._document_store = document_store
        self._paragraph_store = paragraph_store
        self._sentence_store = sentence_store
        self._interpretation_run_store = interpretation_run_store
        self._sentence_interpretation_store = sentence_interpretation_store
        self._mention_store = mention_store
        self._claim_store = claim_store
        self._space_time_frame_store = space_time_frame_store
        self._local_entity_cluster_repository = local_entity_cluster_repository
        self._claim_fine_splitter = claim_fine_splitter
        self._mention_extractor = MentionExtractor()
        self._claim_quality_gate = ClaimQualityGate()
        self._claim_extractor_v1 = ClaimExtractorV1(quality_gate=self._claim_quality_gate)
        self._space_time_extractor_v1 = SpaceTimeExtractorV1()
        self._local_resolver_v1 = LocalResolverV1()
        self._knowledge_cleanup_service = KnowledgeCleanupService(self)
        self._mention_resolution_service = MentionResolutionService(mention_extractor=self._mention_extractor)
        self._information_value_scorer = InformationValueScorer()
        self._claim_payload_builder = ClaimPayloadBuilder(
            claim_extractor=self._claim_extractor_v1,
            quality_gate=self._claim_quality_gate,
            information_value_scorer=self._information_value_scorer,
            resolve_sentence_language=self._resolve_sentence_language,
            build_sentence_mentions=self._build_sentence_mentions,
            build_space_time_frames_for_claims=self._build_space_time_frames_for_claims,
            is_claim_debug_enabled=self._is_claim_debug_enabled,
        )
        self._sentence_unit_builder = SentenceUnitBuilder(
            claim_fine_splitter=claim_fine_splitter,
            information_value_scorer=self._information_value_scorer,
            enable_claim_fine_split_during_parsing=self._ENABLE_CLAIM_FINE_SPLIT_DURING_PARSING,
        )
        self._document_interpretation_service = DocumentInterpretationService(
            interpretation_run_store=self._interpretation_run_store,
            sentence_interpretation_store=self._sentence_interpretation_store,
            mention_store=self._mention_store,
            claim_store=self._claim_store,
            space_time_frame_store=self._space_time_frame_store,
            build_sentence_mentions=self._build_sentence_mentions,
            resolve_sentence_language=self._resolve_sentence_language,
            build_sentence_claim_payload=self._build_sentence_claim_payload,
            finalize_sentence_after_subject_context=self._finalize_sentence_after_subject_context,
            resolve_and_persist_local_entity_clusters=self._resolve_and_persist_local_entity_clusters,
            load_existing_semantic_blocks=self._load_existing_semantic_blocks,
            load_existing_search_profiles=self._load_existing_search_profiles,
            load_existing_global_profiles=self._load_existing_global_profiles,
            is_missing_table_error=self._knowledge_cleanup_service.is_missing_table_error,
            truncate_error_message=self._truncate_error_message,
            interpretation_error_message_max=self._INTERPRETATION_ERROR_MESSAGE_MAX,
        )
        self._trace_service = KnowledgeTraceService(
            ingest_run_store=self._ingest_run_store,
            ingest_item_store=self._ingest_item_store,
            source_store=self._source_store,
            document_store=self._document_store,
            sentence_store=self._sentence_store,
            mention_store=self._mention_store,
            claim_store=self._claim_store,
            space_time_frame_store=self._space_time_frame_store,
            interpretation_run_store=self._interpretation_run_store,
            local_entity_cluster_repository=self._local_entity_cluster_repository,
        )
        self._index_profile_store = index_profile_store
        self._index_build_store = index_build_store
        self._query_run_store = query_run_store
        self._chunk_builder = chunk_builder
        self._chunking_service = ChunkingService(chunk_builder=chunk_builder)
        self._retrieval_engine = retrieval_engine
        self._context_builder = context_builder
        self._vector_index_factory = vector_index_factory
        self._metrics_store = metrics_store
        self._object_storage = object_storage
        self._source_storage_service = source_storage_service or SourceStorageService(object_storage)
        self._knowledge_audit_service = KnowledgeAuditService(ingest_event_store=self._ingest_event_store)
        self._knowledge_feedback_service = KnowledgeFeedbackService(self)
        self._lineage_service = KnowledgeLineageService(self)
        self._report_service = KnowledgeReportService(self)
        self._source_access_service = SourceAccessService(self)
        self._index_build_locks: dict[str, threading.Lock] = {}
        self._index_build_locks_guard = threading.Lock()
        self._knowledge_pii_service = KnowledgePiiService.from_corpus_store(corpus_store)
        self._url_fetch_service = UrlFetchService(text_normalizer=self._normalize_parser_text)
        self._knowledge_permission_service = KnowledgePermissionService(
            corpus_store=self._corpus_store,
            user_repo_list_all=self._user_repo_list_all,
            corpus_mapper=self._to_corpus,
            list_all_unfiltered=self.list_all_unfiltered,
        )
        self._index_build_service = IndexBuildService(
            corpus_store=self._corpus_store,
            source_store=self._source_store,
            index_build_store=self._index_build_store,
            metrics_store=self._metrics_store,
            vector_index_factory=self._vector_index_factory,
            chunking_service=self._chunking_service,
            default_index_profile=self._default_index_profile,
            vector_size_for_profile=self._vector_size_for_profile,
            load_existing_retrieval_chunks=lambda **kwargs: self._load_existing_retrieval_chunks(**kwargs),
            load_existing_semantic_blocks=lambda **kwargs: self._load_existing_semantic_blocks(**kwargs),
            log_step=self._log_step,
            index_build_lock=self._index_build_lock,
            retry_count=self._INDEX_BUILD_RETRY_COUNT,
            retry_backoff_sec=self._INDEX_BUILD_RETRY_BACKOFF_SEC,
            stale_after_sec=self._STALE_INDEX_BUILD_FAIL_AFTER_SEC,
        )
        self._retrieval_service = RetrievalService(
            source_store=self._source_store,
            document_store=self._document_store,
            corpus_store=self._corpus_store,
            source_display_type=self._source_access_service.source_display_type,
            source_created_by_label=self._source_access_service.source_created_by_label,
            dependency_host=self,
        )
        self._parser_orchestrator = ParserOrchestrator(
            source_store=self._source_store,
            parser_run_store=self._parser_run_store,
            document_store=self._document_store,
            paragraph_store=self._paragraph_store,
            sentence_store=self._sentence_store,
            extract_parser_document_from_source=self._extract_parser_document_from_source,
            delete_source_parse_outputs=self._delete_source_parse_outputs,
            normalize_parser_text=self._normalize_parser_text,
            describe_empty_extraction=self._describe_empty_extraction,
            split_paragraphs=self._split_paragraphs,
            build_claim_refinement_budget=self._build_claim_refinement_budget,
            build_sentence_units_for_paragraph_with_diagnostics=self._build_sentence_units_for_paragraph_with_diagnostics,
            interpret_document=self._interpret_document,
            truncate_error_message=self._truncate_error_message,
            log_step=self._log_step,
            parser_error_message_max=self._PARSER_ERROR_MESSAGE_MAX,
            claim_fine_split_early_stop_after_blocks=self._CLAIM_FINE_SPLIT_EARLY_STOP_AFTER_BLOCKS,
            claim_fine_split_min_hit_blocks_to_continue=self._CLAIM_FINE_SPLIT_MIN_HIT_BLOCKS_TO_CONTINUE,
        )
        self._ingest_progress_service = IngestProgressService(
            ingest_item_store=self._ingest_item_store,
            refresh_ingest_run=self._refresh_ingest_run,
        )
        self._ingest_item_processor = IngestItemProcessor(self, progress_service=self._ingest_progress_service)
        self._ingest_run_processor = IngestRunProcessor(self, item_processor=self._ingest_item_processor)
        self._ingest_run_creation_service = IngestRunCreationService(
            self,
            progress_service=self._ingest_progress_service,
        )

    def _ingest_runs(self) -> IngestRunService:
        return IngestRunService(
            ingest_run_store=self._ingest_run_store,
            ingest_item_store=self._ingest_item_store,
            progress_summary_builder=self._ingest_progress_service.build_run_summary,
            quality_diagnostics_builder=_aggregate_ingest_item_quality,
        )

    def _log_step(self, step: str, *, status: str, tenant: str | None = None, duration_ms: float | None = None, **counts: object) -> None:
        payload = {
            "step": step,
            "status": status,
            "tenant": tenant,
            "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        }
        payload.update(counts)
        logger.info("knowledge.pipeline", extra={"knowledge": payload})

    @staticmethod
    def _delete_for_corpus_if_table_exists(store: Any, corpus_uuid: str, *, table_name: str) -> int:
        return KnowledgeCleanupService.delete_for_corpus_if_table_exists(store, corpus_uuid, table_name=table_name)

    @staticmethod
    def _delete_for_document_if_table_exists(store: Any, document_id: str, *, table_name: str) -> int:
        return KnowledgeCleanupService.delete_for_document_if_table_exists(store, document_id, table_name=table_name)

    @staticmethod
    def _is_missing_table_error(exc: Exception, *table_names: str) -> bool:
        return KnowledgeCleanupService.is_missing_table_error(exc, *table_names)

    @staticmethod
    def _truncate_error_message(value: Any, *, max_length: int) -> str:
        text = str(value or "").strip()
        if len(text) <= max_length:
            return text
        suffix = "... [truncated]"
        keep = max(0, max_length - len(suffix))
        return f"{text[:keep]}{suffix}"

    def _load_existing_search_profiles(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[SearchProfile]:
        if self._interpretation_run_store is None:
            return []
        list_for_corpus = getattr(self._interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            return []
        try:
            runs = list_for_corpus(corpus_uuid, limit=limit)
        except ProgrammingError as exc:
            if self._knowledge_cleanup_service.is_missing_table_error(exc, "knowledge_interpretation_runs"):
                return []
            raise
        profiles: list[SearchProfile] = []
        for previous_run in runs:
            if str(previous_run.id) == str(exclude_interpretation_run_id or ""):
                continue
            if previous_run.status != "completed":
                continue
            metadata = dict(previous_run.metadata or {})
            for item in metadata.get("search_profiles") or []:
                profile = _search_profile_from_trace_payload(item) if isinstance(item, dict) else None
                if profile is not None:
                    profiles.append(profile)
        return profiles

    def _load_existing_global_profiles(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if self._interpretation_run_store is None:
            return []
        list_for_corpus = getattr(self._interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            return []
        try:
            runs = list_for_corpus(corpus_uuid, limit=limit)
        except ProgrammingError as exc:
            if self._knowledge_cleanup_service.is_missing_table_error(exc, "knowledge_interpretation_runs"):
                return []
            raise
        profiles_by_id: dict[str, dict[str, Any]] = {}
        for previous_run in reversed(runs):
            if str(previous_run.id) == str(exclude_interpretation_run_id or ""):
                continue
            if previous_run.status != "completed":
                continue
            metadata = dict(previous_run.metadata or {})
            for item in metadata.get("global_profiles") or []:
                if not isinstance(item, dict):
                    continue
                profile_id = str(item.get("profile_id") or "")
                if not profile_id:
                    continue
                profiles_by_id[profile_id] = dict(item)
        return list(profiles_by_id.values())

    def _load_existing_retrieval_chunks(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if self._interpretation_run_store is None:
            return []
        list_for_corpus = getattr(self._interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            return []
        try:
            runs = list_for_corpus(corpus_uuid, limit=limit)
        except ProgrammingError as exc:
            if self._knowledge_cleanup_service.is_missing_table_error(exc, "knowledge_interpretation_runs"):
                return []
            raise
        chunks_by_profile_id: dict[str, dict[str, Any]] = {}
        for previous_run in reversed(runs):
            if str(previous_run.id) == str(exclude_interpretation_run_id or ""):
                continue
            if previous_run.status != "completed":
                continue
            metadata = dict(previous_run.metadata or {})
            for item in metadata.get("retrieval_chunks") or []:
                if not isinstance(item, dict):
                    continue
                profile_id = str(item.get("profile_id") or "")
                if not profile_id:
                    continue
                chunks_by_profile_id[profile_id] = dict(item)
        return list(chunks_by_profile_id.values())

    def _load_existing_semantic_blocks(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if self._interpretation_run_store is None:
            return []
        list_for_corpus = getattr(self._interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            return []
        try:
            runs = list_for_corpus(corpus_uuid, limit=limit)
        except ProgrammingError as exc:
            if self._knowledge_cleanup_service.is_missing_table_error(exc, "knowledge_interpretation_runs"):
                return []
            raise
        blocks_by_id: dict[str, dict[str, Any]] = {}
        for previous_run in reversed(runs):
            if str(previous_run.id) == str(exclude_interpretation_run_id or ""):
                continue
            if previous_run.status != "completed":
                continue
            metadata = dict(previous_run.metadata or {})
            for item in metadata.get("semantic_blocks") or []:
                if not isinstance(item, dict):
                    continue
                block_id = str(item.get("id") or "")
                if not block_id:
                    continue
                blocks_by_id[block_id] = dict(item)
        return list(blocks_by_id.values())

    @staticmethod
    def _semantic_block_search_text(block: dict[str, Any]) -> str:
        return semantic_block_search_text(block)

    @staticmethod
    def _query_terms_for_blocks(query_profile: dict[str, Any] | None, query: str | None) -> set[str]:
        return query_terms_for_blocks(query_profile, query)

    @staticmethod
    def _query_phrase_for_blocks(query: str | None) -> str:
        return query_phrase_for_blocks(query)

    @staticmethod
    def _is_broad_function_query(query: str | None, query_profile: dict[str, Any] | None) -> bool:
        return is_broad_function_query(query, query_profile)

    @staticmethod
    def _select_semantic_blocks_for_query(
        *,
        semantic_blocks: list[dict[str, Any]],
        matched_claims: list[dict[str, Any]],
        matched_chunks: list[dict[str, Any]],
        query_profile: dict[str, Any] | None = None,
        query: str | None = None,
        max_blocks: int = 4,
    ) -> list[dict[str, Any]]:
        return select_semantic_blocks_for_query(
            semantic_blocks=semantic_blocks,
            matched_claims=matched_claims,
            matched_chunks=matched_chunks,
            query_profile=query_profile,
            query=query,
            max_blocks=max_blocks,
        )

    @staticmethod
    def _semantic_blocks_context(blocks: list[dict[str, Any]], *, max_chars: int = 6000) -> str:
        return semantic_blocks_context(blocks, max_chars=max_chars)

    @staticmethod
    def _filter_relevant_semantic_blocks(
        blocks: list[dict[str, Any]],
        *,
        max_blocks: int = 4,
        score_floor: float = 0.25,
        relative_floor_ratio: float = 0.8,
    ) -> list[dict[str, Any]]:
        return filter_relevant_semantic_blocks(
            blocks,
            max_blocks=max_blocks,
            score_floor=score_floor,
            relative_floor_ratio=relative_floor_ratio,
        )

    @staticmethod
    def _retrieval_chunks_from_vector_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return retrieval_chunks_from_vector_hits(hits)

    @staticmethod
    def _semantic_blocks_from_vector_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return semantic_blocks_from_vector_hits(hits)

    @staticmethod
    def _order_chunks_by_vector_hits(retrieval_chunks: list[dict[str, Any]], hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return order_chunks_by_vector_hits(retrieval_chunks, hits)

    @staticmethod
    def _to_corpus(item: Any, *, tenant: str = "") -> Corpus:
        return Corpus(
            id=getattr(item, "id", None),
            tenant=tenant,
            uuid=str(getattr(item, "uuid")),
            name=str(getattr(item, "name")),
            description=getattr(item, "description", None),
            qdrant_collection_name=str(getattr(item, "qdrant_collection_name")),
            created_at=getattr(item, "created_at", None),
            updated_at=getattr(item, "updated_at", None),
            personal_data_mode=str(getattr(item, "personal_data_mode", "no_personal_data")),
            personal_data_sensitivity=str(getattr(item, "personal_data_sensitivity", "medium")),
            pii_depersonalization_enabled=bool(getattr(item, "pii_depersonalization_enabled", True)),
            deleted_at=getattr(item, "deleted_at", None),
            deleted_display_name=getattr(item, "deleted_display_name", None),
            deleted_training_char_count=max(0, int(getattr(item, "deleted_training_char_count", 0) or 0)),
        )

    def _user_repo_list_all(self) -> list[Any]:
        if self._user_repo is None or not hasattr(self._user_repo, "list_all"):
            return []
        return self._user_repo.list_all()

    def _default_index_profile(self, key: str | None = None) -> IndexProfile:
        if key:
            profile = self._index_profile_store.get(key)
            if profile is not None:
                return profile
        return DEFAULT_INDEX_PROFILE

    @staticmethod
    def _vector_size_for_profile(profile: IndexProfile, vector_index: Any) -> int | None:
        config = dict(profile.config or {})
        configured = config.get("vector_size")
        if configured is not None:
            try:
                value = int(configured)
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass
        runtime_size = getattr(vector_index, "vector_size", None)
        try:
            value = int(runtime_size)
            return value if value > 0 else None
        except (TypeError, ValueError):
            return None

    def _index_build_lock(self, build_id: str) -> threading.Lock:
        with self._index_build_locks_guard:
            lock = self._index_build_locks.get(build_id)
            if lock is None:
                lock = threading.Lock()
                self._index_build_locks[build_id] = lock
            return lock

    @staticmethod
    def _sha256_bytes(content: bytes) -> str:
        return IngestRunCreationService._sha256_bytes(content)

    @staticmethod
    def _sha256_text(content: str) -> str:
        return IngestRunCreationService._sha256_text(content)

    @staticmethod
    def _ingest_pipeline_version() -> str:
        return IngestRunCreationService.ingest_pipeline_version()

    @classmethod
    def _ingest_idempotency_key(cls, *, corpus_uuid: str, content_hash: str, pipeline_version: str | None = None) -> str:
        return IngestRunCreationService.ingest_idempotency_key(
            corpus_uuid=corpus_uuid,
            content_hash=content_hash,
            pipeline_version=pipeline_version,
        )

    def _record_ingest_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        item_id: str | None = None,
        message: str | None = None,
        created_by: int | None = None,
        **details: Any,
    ) -> IngestEvent:
        return self._ingest_run_creation_service.record_ingest_event(
            run_id=run_id,
            event_type=event_type,
            status=status,
            item_id=item_id,
            message=message,
            created_by=created_by,
            **details,
        )

    @staticmethod
    def _normalize_parser_text(value: str | None) -> str:
        return SentenceUnitBuilder.normalize_parser_text(value)

    @staticmethod
    def _describe_empty_extraction(metadata: dict[str, Any] | None) -> str:
        info = dict(metadata or {})
        if info.get("source_format") == "pdf" and info.get("no_extractable_text"):
            page_count = int(info.get("page_count") or 0)
            producer = str(info.get("pdf_producer") or "").strip()
            creator = str(info.get("pdf_creator") or "").strip()
            title = str(info.get("pdf_title") or "").strip()
            details: list[str] = []
            if page_count > 0:
                details.append(f"{page_count} oldalas PDF")
            if producer:
                details.append(f"producer: {producer}")
            if creator:
                details.append(f"creator: {creator}")
            if title:
                details.append(f"cím: {title}")
            detail_text = f" ({'; '.join(details)})" if details else ""
            return (
                "A PDF-ből nem nyerhető ki szöveg, mert nem tartalmaz kiolvasható szövegréteget"
                f"{detail_text}. Valószínűleg képalapú vagy szkennelt PDF, ezért OCR szükséges."
            )
        return "A forrásból nem nyerhető ki feldolgozható szöveg."

    @staticmethod
    def _split_paragraphs(text: str) -> list[str]:
        return SentenceUnitBuilder.split_paragraphs(text)

    @staticmethod
    def _normalize_sentence_candidate_text(value: str) -> str:
        return SentenceUnitBuilder.normalize_sentence_candidate_text(value)

    @staticmethod
    def _sentence_word_count(value: str) -> int:
        return SentenceUnitBuilder.sentence_word_count(value)

    @staticmethod
    def _looks_like_noise_sentence_candidate(text: str) -> bool:
        return SentenceUnitBuilder.looks_like_noise_sentence_candidate(text)

    @staticmethod
    def _next_token(text: str, start_idx: int) -> str:
        return SentenceUnitBuilder.next_token(text, start_idx)

    @staticmethod
    def _token_with_period_before(text: str, end_idx: int) -> str:
        return SentenceUnitBuilder.token_with_period_before(text, end_idx)

    @staticmethod
    def _is_abbreviation_boundary(text: str, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_abbreviation_boundary(text, end_idx)

    @staticmethod
    def _is_date_boundary(text: str, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_date_boundary(text, end_idx)

    @staticmethod
    def _is_dotted_abbreviation_continuation(text: str, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_dotted_abbreviation_continuation(text, end_idx)

    @staticmethod
    def _is_legal_reference_boundary(text: str, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_legal_reference_boundary(text, end_idx)

    @staticmethod
    def _is_numeric_list_boundary(text: str, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_numeric_list_boundary(text, end_idx)

    @staticmethod
    def _is_marker_only_fragment(text: str, start_idx: int, end_idx: int) -> bool:
        return SentenceUnitBuilder.is_marker_only_fragment(text, start_idx, end_idx)

    @staticmethod
    def _split_heading_sentence_candidates(text: str) -> list[SentenceCandidate]:
        return SentenceUnitBuilder.split_heading_sentence_candidates(text)

    @staticmethod
    def _is_parenthesized_list_marker_start(text: str, marker_start: int) -> bool:
        return SentenceUnitBuilder.is_parenthesized_list_marker_start(text, marker_start)

    @staticmethod
    def _is_inline_heading_marker_start(text: str, marker_start: int, marker_end: int) -> bool:
        return SentenceUnitBuilder.is_inline_heading_marker_start(text, marker_start, marker_end)

    @staticmethod
    def _build_sentence_candidate(
        text: str,
        start: int,
        end: int,
        *,
        confidence: float,
        split_reason: str,
        block_type: str | None = None,
    ) -> SentenceCandidate | None:
        return SentenceUnitBuilder.build_sentence_candidate(
            text,
            start,
            end,
            confidence=confidence,
            split_reason=split_reason,
            block_type=block_type,
        )

    @staticmethod
    def _long_segment_break_index(text: str, start: int, end: int) -> int | None:
        return SentenceUnitBuilder.long_segment_break_index(text, start, end)

    @staticmethod
    def _split_long_candidate(candidate: SentenceCandidate) -> list[SentenceCandidate]:
        return SentenceUnitBuilder.split_long_candidate(candidate)

    @staticmethod
    def _split_sentence_candidates(text: str, *, block_type: str | None = None) -> list[SentenceCandidate]:
        return SentenceUnitBuilder.split_sentence_candidates(text, block_type=block_type)

    @staticmethod
    def _split_sentences(text: str, *, block_type: str | None = None) -> list[str]:
        return SentenceUnitBuilder.split_sentences(text, block_type=block_type)

    @staticmethod
    def _build_table_sentence_units(paragraph_text: str, paragraph_metadata: dict[str, Any]) -> list[dict[str, Any]]:
        return SentenceUnitBuilder.build_table_sentence_units(paragraph_text, paragraph_metadata)

    @classmethod
    def _is_strong_sentence_candidate(cls, candidate: SentenceCandidate) -> bool:
        return SentenceUnitBuilder.is_strong_sentence_candidate(candidate)

    @classmethod
    def _build_claim_refinement_budget(cls, total_blocks: int) -> int:
        return InformationValueScorer.build_claim_refinement_budget(total_blocks)

    @classmethod
    def _count_claim_refinement_signals(cls, text: str) -> dict[str, int]:
        return InformationValueScorer.count_claim_refinement_signals(text)

    @classmethod
    def _should_attempt_claim_refinement(
        cls,
        candidate: SentenceCandidate,
        *,
        block_type: str,
        refinement_state: dict[str, Any] | None = None,
    ) -> tuple[bool, str, dict[str, int]]:
        return InformationValueScorer.should_attempt_claim_refinement(
            candidate,
            block_type=block_type,
            refinement_state=refinement_state,
        )

    @staticmethod
    def _language_tag_from_metadata(metadata: dict[str, Any]) -> str | None:
        return SentenceUnitBuilder.language_tag_from_metadata(metadata)

    @staticmethod
    def _sentence_unit_from_candidate(candidate: SentenceCandidate, *, strong_split: bool) -> dict[str, Any]:
        return SentenceUnitBuilder.sentence_unit_from_candidate(candidate, strong_split=strong_split)

    def _refine_candidate_with_claim_splitter(
        self,
        paragraph_text: str,
        candidate: SentenceCandidate,
        *,
        paragraph_metadata: dict[str, Any],
    ) -> list[dict[str, Any]] | None:
        return self._sentence_unit_builder.refine_candidate_with_claim_splitter(
            paragraph_text,
            candidate,
            paragraph_metadata=paragraph_metadata,
        )

    def _build_sentence_units_for_paragraph(
        self,
        paragraph_text: str,
        *,
        block_type: str,
        paragraph_metadata: dict[str, Any],
        refinement_state: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return self._sentence_unit_builder.build_sentence_units_for_paragraph(
            paragraph_text,
            block_type=block_type,
            paragraph_metadata=paragraph_metadata,
            refinement_state=refinement_state,
        )

    def _build_sentence_units_for_paragraph_with_diagnostics(
        self,
        paragraph_text: str,
        *,
        block_type: str,
        paragraph_metadata: dict[str, Any],
        refinement_state: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return self._sentence_unit_builder.build_sentence_units_for_paragraph_with_diagnostics(
            paragraph_text,
            block_type=block_type,
            paragraph_metadata=paragraph_metadata,
            refinement_state=refinement_state,
        )

    @staticmethod
    def _detect_assertion_mode(text: str) -> str:
        return ClaimPayloadBuilder.detect_assertion_mode(text)

    @staticmethod
    def _detect_time_framing(text: str, *, assertion_mode: str) -> tuple[str, str | None]:
        return ClaimPayloadBuilder.detect_time_framing(text, assertion_mode=assertion_mode)

    @staticmethod
    def _detect_space_framing(text: str, mentions: list[Mention]) -> tuple[str, str | None]:
        return ClaimPayloadBuilder.detect_space_framing(text, mentions)

    @staticmethod
    def _detect_claim_type(text: str, *, assertion_mode: str, mentions: list[Mention]) -> str:
        return ClaimPayloadBuilder.detect_claim_type(text, assertion_mode=assertion_mode, mentions=mentions)

    @staticmethod
    def _mention_patterns() -> list[tuple[str, str]]:
        return MentionResolutionService.mention_patterns()

    def _build_mentions_for_sentence(self, sentence: Sentence) -> list[Mention]:
        return self._mention_resolution_service.build_mentions_for_sentence(sentence)

    @staticmethod
    def _align_extracted_mentions_to_sentence(sentence: Sentence, mentions: list[Mention]) -> list[Mention]:
        return MentionResolutionService.align_extracted_mentions_to_sentence(sentence, mentions)

    @staticmethod
    def _merge_sentence_mentions(extracted_mentions: list[Mention], heuristic_mentions: list[Mention]) -> list[Mention]:
        return MentionResolutionService.merge_sentence_mentions(extracted_mentions, heuristic_mentions)

    @staticmethod
    def _is_mention_debug_enabled(*, source: Source | None, document: Document | None, sentence: Sentence) -> bool:
        return bool(
            getattr(settings, "DEBUG_MENTION", False)
            or getattr(settings, "debug_mention", False)
            or sentence.metadata.get("mention_debug")
            or sentence.metadata.get("debug_mentions")
            or getattr(document, "metadata", {}).get("mention_debug")
            or getattr(source, "metadata", {}).get("mention_debug")
        )

    @staticmethod
    def _is_claim_debug_enabled(*, source: Source | None, document: Document | None, sentence: Sentence) -> bool:
        return bool(
            getattr(settings, "DEBUG_CLAIM", False)
            or getattr(settings, "debug_claim", False)
            or sentence.metadata.get("claim_debug")
            or sentence.metadata.get("debug_claims")
            or getattr(document, "metadata", {}).get("claim_debug")
            or getattr(source, "metadata", {}).get("claim_debug")
        )

    @staticmethod
    def _is_space_time_debug_enabled(*, source: Source | None, document: Document | None, sentence: Sentence) -> bool:
        return bool(
            getattr(settings, "DEBUG_SPACE_TIME", False)
            or getattr(settings, "debug_space_time", False)
            or sentence.metadata.get("space_time_debug")
            or sentence.metadata.get("debug_space_time")
            or getattr(document, "metadata", {}).get("space_time_debug")
            or getattr(source, "metadata", {}).get("space_time_debug")
        )

    @staticmethod
    def _claim_extractor_version() -> str:
        version = str(getattr(settings, "CLAIM_EXTRACTOR_VERSION", "v1") or "v1").strip().lower()
        return "v1" if version != "v1" else version

    @staticmethod
    def _resolve_sentence_language(
        sentence: Sentence,
        *,
        source: Source | None = None,
        document: Document | None = None,
    ) -> str:
        source_language = None
        if source is not None and isinstance(source.metadata, dict):
            source_language = source.metadata.get("language") or source.metadata.get("language_tag")
        preferred_language = (
            sentence.metadata.get("language")
            or sentence.metadata.get("language_tag")
            or getattr(document, "language", None)
            or source_language
        )
        return detect_language(sentence.text_content, preferred_language=preferred_language) or resolve_language(
            text=sentence.text_content,
            language=preferred_language,
        )

    def _build_sentence_mentions(
        self,
        sentence: Sentence,
        *,
        source: Source | None = None,
        document: Document | None = None,
    ) -> list[Mention]:
        language = self._resolve_sentence_language(sentence, source=source, document=document)
        sentence_mentions = self._mention_resolution_service.build_sentence_mentions(sentence, language=language)
        logger.debug(
            "[MENTION PIPELINE]\nsentence_id=%s\nmention_count=%s",
            sentence.id,
            len(sentence_mentions),
        )
        if self._is_mention_debug_enabled(source=source, document=document, sentence=sentence):
            debug_print_mentions(sentence, sentence_mentions, language=language)
        return sentence_mentions

    def _build_space_time_frames_for_claims(
        self,
        *,
        sentence: Sentence,
        claims: list[Claim],
        language: str,
        source: Source | None = None,
        document: Document | None = None,
        emit_logs: bool = True,
    ) -> tuple[list[Claim], list[SpaceTimeFrame]]:
        updated_claims: list[Claim] = []
        frames: list[SpaceTimeFrame] = []
        for claim in claims:
            updated_claim, frame = self.build_and_attach_space_time_frame(
                claim=claim,
                sentence=sentence,
                language=language,
                source=source,
                document=document,
                emit_logs=emit_logs,
            )
            updated_claims.append(updated_claim)
            frames.append(frame)
        return updated_claims, frames

    def build_and_attach_space_time_frame(
        self,
        *,
        claim: Claim,
        sentence: Sentence,
        language: str,
        source: Source | None = None,
        document: Document | None = None,
        emit_logs: bool = True,
    ) -> tuple[Claim, SpaceTimeFrame]:
        frame = self._space_time_extractor_v1.extract(claim, sentence, language=language)
        if claim.space_time_frame_id:
            frame = replace(frame, id=claim.space_time_frame_id)
        updated_claim = replace(
            claim,
            space_time_frame_id=frame.frame_id,
            time_mode=frame.time_mode,
            time_label=frame.time_value,
            space_mode=frame.space_mode,
            space_label=frame.space_value,
            metadata={
                **dict(claim.metadata or {}),
                "space_time_frame_id": frame.frame_id,
                "space_time_language": frame.language,
                "space_time_frame_time_mode": frame.time_mode,
                "space_time_frame_space_mode": frame.space_mode,
                "space_time_frame_confidence": frame.overall_confidence,
            },
        )
        if emit_logs:
            logger.debug(
                "[SPACE-TIME PIPELINE]\nsentence_id=%s\nclaim_id=%s\nframe_id=%s\ntime_mode=%s\nspace_mode=%s\nconfidence=%s",
                sentence.id,
                updated_claim.claim_id,
                frame.frame_id,
                frame.time_mode,
                frame.space_mode,
                frame.overall_confidence,
            )
            if self._is_space_time_debug_enabled(source=source, document=document, sentence=sentence):
                SpaceTimeExtractorV1.debug_print(updated_claim, frame)
        return updated_claim, frame

    def _build_sentence_claim_payload(
        self,
        sentence: Sentence,
        mentions: list[Mention],
        *,
        source: Source | None = None,
        document: Document | None = None,
        defer_space_time: bool = False,
    ) -> tuple[SentenceInterpretation, list[Claim], list[SpaceTimeFrame]]:
        return self._claim_payload_builder.build_sentence_claim_payload(
            sentence=sentence,
            mentions=mentions,
            source=source,
            document=document,
            defer_space_time=defer_space_time,
        )

    def _finalize_sentence_after_subject_context(
        self,
        sentence: Sentence,
        mentions: list[Mention],
        interpretation: SentenceInterpretation,
        claims: list[Claim],
        *,
        language: str,
        source: Source | None = None,
        document: Document | None = None,
    ) -> tuple[SentenceInterpretation, list[Claim], list[SpaceTimeFrame]]:
        return self._claim_payload_builder.finalize_sentence_after_subject_context(
            sentence=sentence,
            mentions=mentions,
            interpretation=interpretation,
            claims=claims,
            language=language,
            source=source,
            document=document,
        )

    def get_ingest_run_trace(
        self,
        run_id: str,
        *,
        log_level: str | None = "FULL_TRACE",
        debug: bool = False,
    ) -> dict[str, Any] | None:
        return self._trace_service.build_trace(run_id, log_level=log_level, debug=debug)

    def _log_ingest_trace_summary(self, run_id: str) -> None:
        trace = self.get_ingest_run_trace(run_id)
        if trace is None:
            return
        summary = trace.get("summary") or {}
        logger.debug(
            "[KNOWLEDGE TRACE SUMMARY]\nrun_id=%s\nsource_id=%s\nlanguage=%s\nsentence_count=%s\nmention_count=%s\nclaim_count=%s\nspace_time_frame_count=%s\nlocal_entity_cluster_count=%s\nlocal_entity_count=%s\nlow_coherence_local_entity_count=%s\nunknown_entity_type_count=%s",
            trace["run_id"],
            trace.get("source_id"),
            trace.get("language", "unknown"),
            summary.get("sentence_count", 0),
            summary.get("mention_count", 0),
            summary.get("claim_count", 0),
            summary.get("space_time_frame_count", 0),
            summary.get("local_entity_cluster_count", 0),
            summary.get("local_entity_count", 0),
            summary.get("low_coherence_local_entity_count", 0),
            summary.get("unknown_entity_type_count", 0),
        )

    @staticmethod
    def _detect_predicate(text: str) -> tuple[str, int]:
        return ClaimPayloadBuilder.detect_predicate(text)

    def _build_claim_for_sentence(self, sentence: Sentence, mentions: list[Mention]) -> tuple[SentenceInterpretation, list[Claim]]:
        return self._claim_payload_builder.build_claim_for_sentence(sentence, mentions)

    def _build_sentence_interpretation_payload(self, sentence: Sentence) -> dict[str, Any]:
        return self._claim_payload_builder.build_sentence_interpretation_payload(sentence)

    def _score_information_value(
        self,
        *,
        sentence: Sentence,
        mentions: list[Mention],
        claim: Claim | None,
        interpretation: SentenceInterpretation,
    ) -> tuple[float, str, str]:
        return self._information_value_scorer.score_information_value(
            sentence=sentence,
            mentions=mentions,
            claim=claim,
            interpretation=interpretation,
        )

    def _resolve_and_persist_local_entity_clusters(
        self,
        *,
        run: InterpretationRun,
        source: Source,
        document: Document,
        sentences: list[Sentence],
        mentions: list[Mention],
        claims: list[Claim],
    ) -> tuple[list[LocalEntityCluster], dict[str, Any]]:
        """Claim / mention / space-time persist után: lokális entitás klaszterek + opcionális DB mentés.

        Újrafuttatás / idempotencia: mentés előtt ``delete_by_run`` (ha a run UUID), különben
        ``delete_by_source``, hogy ne duplikálódjanak a sorok.
        """
        run_uuid = uuid_lib.UUID(run.id) if _is_uuid_string(run.id) else None
        source_uuid = uuid_lib.UUID(source.id) if _is_uuid_string(source.id) else None
        source_language = (
            document.language
            or getattr(source, "language", None)
            or resolve_language(text=sentences[0].text_content if sentences else None)
        )
        local_clusters, local_resolver_trace = self._local_resolver_v1.resolve_with_trace(
            run_uuid,
            source_uuid,
            sentences,
            mentions,
            claims,
            language=source_language,
        )
        logger.debug(
            "[LOCAL RESOLVER V1]\ninterpretation_run_id=%s\ncluster_count=%s\nclaim_count=%s",
            run.id,
            len(local_clusters),
            len(claims),
        )
        repo = self._local_entity_cluster_repository
        if repo is None:
            return local_clusters, local_resolver_trace
        try:
            if run_uuid is not None:
                repo.delete_by_run(run_uuid)
            elif source_uuid is not None:
                repo.delete_by_source(source_uuid)
            if local_clusters:
                repo.save_many(local_clusters)
        except ProgrammingError as exc:
            if self._knowledge_cleanup_service.is_missing_table_error(exc, "knowledge_local_entity_clusters"):
                logger.warning(
                    "knowledge.local_entity_clusters.skip_missing_table",
                    extra={
                        "document_id": document.id,
                        "interpretation_run_id": run.id,
                        "source_id": source.id,
                    },
                )
            else:
                raise
        return local_clusters, local_resolver_trace

    def _interpret_document(
        self,
        *,
        source: Source,
        document: Document,
        sentences: list[Sentence],
        created_by: int | None = None,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> InterpretationRun | None:
        return self._document_interpretation_service.interpret_document(
            source=source,
            document=document,
            sentences=sentences,
            created_by=created_by,
            progress_callback=progress_callback,
        )

    def _extract_parser_document_from_source(
        self,
        source: Source,
        *,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> ExtractedDocument:
        return self._ingest_item_processor._extract_parser_document_from_source(
            source,
            progress_callback=progress_callback,
        )


    def _delete_source_parse_outputs(self, source_id: str) -> None:
        return self._ingest_item_processor._delete_source_parse_outputs(source_id)


    def _is_stale_parser_processing(self, source_id: str, *, updated_at: datetime | None = None) -> bool:
        return self._ingest_item_processor._is_stale_parser_processing(source_id, updated_at=updated_at)


    def is_ingest_item_stale_processing(self, item: IngestItem) -> bool:
        if item.status != "processing":
            return False
        source_id = str(item.source_id or (item.metadata or {}).get("source_id") or "").strip()
        return bool(source_id) and self._is_stale_parser_processing(source_id, updated_at=item.updated_at)

    def _refresh_ingest_run(self, run_id: str) -> IngestRun:
        return self._ingest_runs().recalculate_progress(run_id)

    def _require_corpus(self, corpus_uuid: str) -> Corpus:
        raw = self._corpus_store.get_by_uuid(corpus_uuid)
        if raw is None:
            raise ValueError("Corpus not found")
        return self._to_corpus(raw)

    def _ensure_title(self, value: str | None, *, fallback: str) -> str:
        normalized = str(value or "").strip()
        return (normalized or fallback)[:200]

    def _create_source_from_ingest_item(
        self,
        *,
        tenant: str,
        item: IngestItem,
        ingest_input: IngestInput,
        content_hash: str,
        created_by: int | None,
    ) -> Source:
        return self._ingest_item_processor._create_source_from_ingest_item(
            tenant=tenant,
            item=item,
            ingest_input=ingest_input,
            content_hash=content_hash,
            created_by=created_by,
        )


    def list_all(self, current_user_id: int | None = None, current_user: User | None = None) -> list[Corpus]:
        return self._knowledge_permission_service.list_all(
            current_user_id=current_user_id,
            current_user=current_user,
        )

    def list_all_unfiltered(self) -> list[Corpus]:
        return [self._to_corpus(item) for item in self._corpus_store.list_all()]

    def storage_metrics_for_corpus(self, corpus: Corpus) -> dict[str, Any]:
        file_bytes = 0
        database_bytes = 0
        qdrant_bytes = 0
        qdrant_points = 0
        qdrant_vectors = 0
        training_char_count = 0
        if getattr(corpus, "deleted_at", None) is not None:
            training_char_count = int(getattr(corpus, "deleted_training_char_count", 0) or 0)
            return {
                "file_bytes": 0,
                "database_bytes": 0,
                "qdrant_bytes": 0,
                "total_bytes": 0,
                "qdrant_points": 0,
                "qdrant_vectors": 0,
                "training_char_count": max(0, training_char_count),
            }
        if hasattr(self._ingest_input_store, "uploaded_file_size_bytes_for_corpus"):
            try:
                file_bytes = int(self._ingest_input_store.uploaded_file_size_bytes_for_corpus(corpus.uuid))
            except Exception:
                logger.debug("knowledge.storage_metrics.file_bytes_failed", exc_info=True)
        if hasattr(self._corpus_store, "database_size_bytes_for_corpus"):
            try:
                database_bytes = int(self._corpus_store.database_size_bytes_for_corpus(corpus.uuid))
            except Exception:
                logger.debug("knowledge.storage_metrics.database_bytes_failed", exc_info=True)
        collection_names = {
            str(corpus.qdrant_collection_name or "").strip(),
            *{
                str(build.collection_name or "").strip()
                for build in self._index_build_store.list_for_corpus(corpus.uuid)
                if str(build.collection_name or "").strip()
            },
        }
        collection_names.discard("")
        if collection_names:
            try:
                vector_index = self._vector_index_factory()
                stats_fn = getattr(vector_index, "collection_storage_stats", None)
                if callable(stats_fn):
                    for collection_name in collection_names:
                        stats = stats_fn(collection_name)
                        qdrant_bytes += int(stats.get("estimated_bytes") or 0)
                        qdrant_points += int(stats.get("points_count") or 0)
                        qdrant_vectors += int(stats.get("vectors_count") or 0)
            except Exception:
                logger.debug("knowledge.storage_metrics.qdrant_bytes_failed", exc_info=True)
        try:
            training_char_count = int(self.ingest_run_list_summary(corpus.uuid).get("total_char_count") or 0)
        except Exception:
            logger.debug("knowledge.storage_metrics.training_chars_failed", exc_info=True)
        total_bytes = file_bytes + database_bytes + qdrant_bytes
        return {
            "file_bytes": max(0, file_bytes),
            "database_bytes": max(0, database_bytes),
            "qdrant_bytes": max(0, qdrant_bytes),
            "total_bytes": max(0, total_bytes),
            "qdrant_points": max(0, qdrant_points),
            "qdrant_vectors": max(0, qdrant_vectors),
            "training_char_count": max(0, training_char_count),
        }

    def qdrant_collection_for_uuid(self, kb_uuid: str) -> str | None:
        kb = self._corpus_store.get_by_uuid(kb_uuid)
        if not kb:
            return None
        return str(getattr(kb, "qdrant_collection_name"))

    def detect_pii_matches(self, *, text: str, sensitivity: str = "medium") -> list[tuple[int, int, str, str]]:
        return self._knowledge_pii_service.detect_matches(text=text, sensitivity=sensitivity)

    def resolve_or_create_pii_token(self, *, corpus_uuid: str, entity_type: str, original_value: str) -> str:
        return self._knowledge_pii_service.resolve_or_create_token(
            corpus_uuid=corpus_uuid,
            entity_type=entity_type,
            original_value=original_value,
        )

    def resolve_pii_tokens(self, *, corpus_uuid: str, tokens: list[str]) -> dict[str, str]:
        return self._knowledge_pii_service.resolve_tokens(corpus_uuid=corpus_uuid, tokens=tokens)

    def get_trainable_kb_ids(self, user_id: int, user: User | None) -> set[int]:
        return self._knowledge_permission_service.get_trainable_kb_ids(user_id, user)

    def create(
        self,
        name: str,
        description: str | None = None,
        permissions: list[tuple[int, str]] | None = None,
        pii_depersonalization_enabled: bool = True,
        current_user_id: int | None = None,
    ) -> Corpus:
        if self._corpus_store.get_by_name(name):
            raise ValueError("KB name already exists")
        if current_user_id is None:
            raise ValueError("Current user is required")
        corpus_uuid = str(uuid_lib.uuid4())
        corpus = Corpus(
            id=None,
            tenant="",
            uuid=corpus_uuid,
            name=name,
            description=description,
            qdrant_collection_name=f"kb_{corpus_uuid}",
            pii_depersonalization_enabled=bool(pii_depersonalization_enabled),
            created_at=None,
            updated_at=None,
        )
        created_raw = self._corpus_store.create(corpus, actor_user_id=current_user_id)
        created = self._to_corpus(created_raw)
        perms = [(uid, perm) for uid, perm in (permissions or []) if perm and perm != "none"]
        if not any(uid == current_user_id for uid, _ in perms):
            perms.append((current_user_id, "train"))
        self._corpus_store.set_permissions(created.uuid, perms, actor_user_id=current_user_id)
        self._metrics_store.increment("corpus_count", 1)
        self._log_step("corpus.create", status="ok", corpus_uuid=created.uuid, permissions=len(perms))
        return created

    def update(
        self,
        uuid: str,
        name: str,
        description: str | None,
        personal_data_mode: str | None = None,
        pii_depersonalization_enabled: bool | None = None,
        current_user_id: int | None = None,
    ) -> Corpus:
        kb = self._corpus_store.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")
        if current_user_id is None:
            raise ValueError("Current user is required")
        corpus = self._to_corpus(kb)
        updated = replace(
            corpus,
            name=name,
            description=description,
            personal_data_mode=personal_data_mode or corpus.personal_data_mode,
            pii_depersonalization_enabled=(
                bool(pii_depersonalization_enabled)
                if pii_depersonalization_enabled is not None
                else corpus.pii_depersonalization_enabled
            ),
        )
        return self._to_corpus(self._corpus_store.update(updated, actor_user_id=current_user_id))

    def delete(self, uuid: str, confirm_name: str | None = None, demo_mode: bool = False) -> None:
        kb = self._corpus_store.get_by_uuid(uuid)
        if not kb:
            raise ValueError("KB not found")
        kb_name = str(getattr(kb, "name", "") or "")
        if confirm_name and confirm_name != kb_name:
            raise ValueError("Confirmation name does not match")
        summary = self.ingest_run_list_summary(uuid)
        training_char_count = int(summary.get("total_char_count") or 0)
        self.clear_contents(uuid, confirm_name=confirm_name)
        self._corpus_store.delete(uuid, training_char_count=training_char_count)
        self._log_step("corpus.delete", status="ok", corpus_uuid=uuid, training_char_count=training_char_count)

    def clear_contents(
        self,
        uuid: str,
        *,
        confirm_name: str | None = None,
        current_user_id: int | None = None,
    ) -> dict[str, int]:
        return self._knowledge_cleanup_service.clear_contents(
            uuid,
            confirm_name=confirm_name,
            current_user_id=current_user_id,
        )

    def get_permissions_with_users(self, kb_uuid: str) -> list[dict[str, Any]]:
        return self._knowledge_permission_service.get_permissions_with_users(kb_uuid)

    def get_permissions_with_users_batch(self, kb_uuids: list[str]) -> dict[str, list[dict[str, Any]]]:
        return self._knowledge_permission_service.get_permissions_with_users_batch(kb_uuids)

    def set_permissions(
        self,
        kb_uuid: str,
        permissions: list[tuple[int, str]],
        current_user_id: int | None = None,
    ) -> None:
        self._knowledge_permission_service.set_permissions(
            kb_uuid,
            permissions,
            current_user_id=current_user_id,
        )

    def user_can_use(self, kb_uuid: str, user_id: int, user: User | None) -> bool:
        return self._knowledge_permission_service.user_can_use(kb_uuid, user_id, user)

    def user_can_train(self, kb_uuid: str, user_id: int, user: User | None) -> bool:
        return self._knowledge_permission_service.user_can_train(kb_uuid, user_id, user)

    def can_view_knowledge_base(self, user: User | None, kb: Corpus | None) -> bool:
        return self._knowledge_permission_service.can_view_knowledge_base(user, kb)

    def can_train_knowledge_base(self, user: User | None, kb: Corpus | None) -> bool:
        return self._knowledge_permission_service.can_train_knowledge_base(user, kb)

    def can_delete_knowledge_base(self, user: User | None, kb: Corpus | None) -> bool:
        return self._knowledge_permission_service.can_delete_knowledge_base(user, kb)

    def can_view_ingest_run(self, user: User | None, run: Any | None) -> bool:
        return self._knowledge_permission_service.can_view_ingest_run(user, run)

    def can_view_ingest_item(self, user: User | None, item: Any | None) -> bool:
        return self._knowledge_permission_service.can_view_ingest_item(user, item)

    def can_reprocess_ingest_item(self, user: User | None, item: Any | None) -> bool:
        return self._knowledge_permission_service.can_reprocess_ingest_item(user, item)

    def can_delete_source(self, user: User | None, source: Any | None) -> bool:
        return self._knowledge_permission_service.can_delete_source(user, source)

    def can_start_index_build(self, user: User | None, kb: Corpus | None) -> bool:
        return self._knowledge_permission_service.can_start_index_build(user, kb)

    def can_view_knowledge_metrics(self, user: User | None) -> bool:
        return self._knowledge_permission_service.can_view_knowledge_metrics(user)

    def create_source(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        title: str,
        source_type: str,
        raw_content: str | None,
        file_ref: str | None,
        created_by: int | None,
    ) -> Source:
        source = Source(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            title=title,
            source_type=source_type,  # type: ignore[arg-type]
            raw_content=raw_content,
            file_ref=file_ref,
            status="attached",
            created_by=created_by,
            metadata={"content_length": len(raw_content or "")},
        )
        self._metrics_store.increment("source_count", 1)
        self._log_step("source.create", status="ok", tenant=tenant, corpus_uuid=corpus_uuid, source_id=source.id)
        return self._source_store.create(source)

    def list_sources(self, corpus_uuid: str) -> list[Source]:
        return self._source_store.list_for_corpus(corpus_uuid)

    def get_source(self, source_id: str) -> Source | None:
        return self._source_store.get(source_id)

    def get_source_content(self, source_id: str) -> dict[str, Any] | None:
        return self._source_access_service.get_source_content(source_id)

    def user_label(self, user_id: int | None) -> str:
        return self._source_access_service.user_label(user_id)

    def get_source_download(self, source_id: str) -> dict[str, Any] | None:
        return self._source_access_service.get_source_download(source_id)

    def get_query_source_download(self, query_run_id: str, source_id: str) -> dict[str, Any] | None:
        return self._source_access_service.get_query_source_download(query_run_id, source_id)

    def get_query_context_download(self, query_run_id: str) -> dict[str, Any] | None:
        return self._source_access_service.get_query_context_download(query_run_id)

    def parse_source(
        self,
        source_id: str,
        *,
        created_by: int | None = None,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> ParserRun:
        return self._parser_orchestrator.parse_source(
            source_id,
            created_by=created_by,
            progress_callback=progress_callback,
        )

    def create_text_ingest_run(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        title: str,
        text: str,
        created_by: int | None,
    ) -> IngestRun:
        return self._ingest_run_creation_service.create_text_run(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            title=title,
            text=text,
            created_by=created_by,
        )

    def create_file_ingest_run(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        files: list[dict[str, Any]],
        created_by: int | None,
    ) -> IngestRun:
        return self._ingest_run_creation_service.create_file_run(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            files=files,
            created_by=created_by,
        )

    def create_url_ingest_run(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        urls: list[dict[str, Any]],
        created_by: int | None,
    ) -> IngestRun:
        return self._ingest_run_creation_service.create_url_run(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            urls=urls,
            created_by=created_by,
        )

    def get_ingest_run(self, run_id: str) -> IngestRun | None:
        run = self._ingest_run_store.get(run_id)
        if run is None:
            return None
        if run.status in {"queued", "processing"}:
            return self._refresh_ingest_run(run_id)
        return run

    def list_ingest_runs(self, corpus_uuid: str, *, limit: int = 20, offset: int = 0) -> list[IngestRun]:
        runs = self._ingest_run_store.list_for_corpus(corpus_uuid, limit=limit, offset=offset)
        refreshed: list[IngestRun] = []
        for run in runs:
            if run.status in {"queued", "processing"}:
                refreshed.append(self._refresh_ingest_run(run.id))
            else:
                refreshed.append(run)
        return refreshed

    def ingest_run_list_summary(self, corpus_uuid: str) -> dict[str, Any]:
        total_run_count = None
        if hasattr(self._ingest_run_store, "count_for_corpus"):
            total_run_count = int(self._ingest_run_store.count_for_corpus(corpus_uuid))
        total_char_count = 0
        total_sentence_count = 0
        if hasattr(self._ingest_item_store, "list_for_corpus"):
            all_items = self._ingest_item_store.list_for_corpus(corpus_uuid)
        else:
            runs = self.list_ingest_runs(corpus_uuid, limit=1000, offset=0)
            all_items = [item for run in runs for item in self.list_ingest_items(run.id)]
            if total_run_count is None:
                total_run_count = len(runs)
        for item in all_items:
            item_char_count = self._ingest_item_char_count(item)
            if item_char_count <= 0 and item.source_id:
                document = self._document_store.get_for_source(item.source_id)
                if document is not None:
                    item_char_count = int(document.char_count or len(document.text_content or ""))
            total_char_count += item_char_count
            total_sentence_count += self._ingest_item_sentence_count(item)
        return {
            "total_run_count": int(total_run_count or 0),
            "total_item_count": len(all_items),
            "total_char_count": total_char_count,
            "total_sentence_count": total_sentence_count,
        }

    def get_ingest_item(self, item_id: str) -> IngestItem | None:
        return self._ingest_item_store.get(item_id)

    def get_ingest_input_for_item(self, item_id: str) -> IngestInput | None:
        return self._ingest_input_store.get_for_item(item_id)

    def get_document_for_ingest_item(self, item_id: str) -> Document | None:
        item = self._ingest_item_store.get(item_id)
        if item is None or not item.source_id:
            return None
        return self._document_store.get_for_source(item.source_id)

    def list_paragraphs_for_ingest_item(self, item_id: str) -> list[Paragraph]:
        document = self.get_document_for_ingest_item(item_id)
        if document is None:
            return []
        return self._paragraph_store.list_for_document(document.id)

    def list_sentences_for_ingest_item(self, item_id: str) -> list[Sentence]:
        document = self.get_document_for_ingest_item(item_id)
        if document is None:
            return []
        sentences = self._sentence_store.list_for_document(document.id)
        enriched_sentences: list[Sentence] = []
        for sentence in sentences:
            detail = self.get_sentence_interpretation(sentence.id)
            interpretation = detail["interpretation"] if detail is not None else None
            if interpretation is None:
                enriched_sentences.append(sentence)
                continue
            enriched_sentences.append(
                replace(
                    sentence,
                    metadata={
                        **sentence.metadata,
                        "information_value_score": interpretation.information_value_score,
                        "information_value_status": interpretation.information_value_status,
                        "information_value_reason": interpretation.information_value_reason,
                    },
                )
            )
        return enriched_sentences

    def get_sentence_interpretation(self, sentence_id: str) -> dict[str, Any] | None:
        sentence = self._sentence_store.get(sentence_id)
        if sentence is None:
            return None

        if (
            self._sentence_interpretation_store is None
            or self._mention_store is None
            or self._claim_store is None
            or self._space_time_frame_store is None
        ):
            return self._build_sentence_interpretation_payload(sentence)
        try:
            interpretation = self._sentence_interpretation_store.get_for_sentence(sentence_id)
        except ProgrammingError as exc:
            if self._knowledge_cleanup_service.is_missing_table_error(
                exc,
                "knowledge_interpretation_runs",
                "knowledge_sentence_interpretations",
                "knowledge_mentions",
                "knowledge_claims",
                "knowledge_space_time_frames",
            ):
                return self._build_sentence_interpretation_payload(sentence)
            raise
        if interpretation is None:
            document = self._document_store.get(sentence.document_id)
            source = self._source_store.get(sentence.source_id)
            if document is not None and source is not None:
                self._interpret_document(
                    source=source,
                    document=document,
                    sentences=self._sentence_store.list_for_document(document.id),
                )
                interpretation = self._sentence_interpretation_store.get_for_sentence(sentence_id)
        if interpretation is None:
            return self._build_sentence_interpretation_payload(sentence)
        return {
            "interpretation": interpretation,
            "mentions": self._mention_store.list_for_sentence(sentence_id),
            "claims": self._claim_store.list_for_sentence(sentence_id),
            "space_time_frames": self._space_time_frame_store.list_for_sentence(sentence_id),
        }

    def read_ingest_file_bytes(self, item_id: str) -> tuple[bytes, str | None, str | None]:
        return self._source_access_service.read_ingest_file_bytes(item_id)

    def list_ingest_items(self, run_id: str) -> list[IngestItem]:
        return self._ingest_item_store.list_for_run(run_id)

    def enrich_ingest_items_with_document_metrics(self, items: list[IngestItem]) -> list[IngestItem]:
        enriched: list[IngestItem] = []
        for item in items:
            metadata = dict(item.metadata or {})
            if self._ingest_item_char_count(item) <= 0 and item.source_id:
                document = self._document_store.get_for_source(item.source_id)
                if document is not None:
                    metadata["char_count"] = int(document.char_count or len(document.text_content or ""))
            enriched.append(replace(item, metadata=metadata) if metadata != (item.metadata or {}) else item)
        return enriched

    @staticmethod
    def _ingest_item_char_count(item: IngestItem) -> int:
        metadata = item.metadata or {}
        for key in ("char_count", "processed_char_count"):
            value = metadata.get(key)
            if isinstance(value, (int, float)):
                return max(0, int(value))
        parser_status = metadata.get("parser_block_status")
        if isinstance(parser_status, dict):
            char_start = parser_status.get("char_start")
            char_end = parser_status.get("char_end")
            if isinstance(char_start, (int, float)) and isinstance(char_end, (int, float)) and char_end >= char_start:
                return int(char_end - char_start)
        return 0

    @staticmethod
    def _ingest_item_sentence_count(item: IngestItem) -> int:
        metadata = item.metadata or {}
        value = metadata.get("sentence_count")
        if isinstance(value, (int, float)):
            return max(0, int(value))
        summary = metadata.get("processing_summary")
        if isinstance(summary, dict):
            progress = summary.get("document_progress")
            if isinstance(progress, dict):
                processed_parts = progress.get("processed_parts")
                total_parts = progress.get("total_parts")
                phase = str(progress.get("phase") or "")
                if phase in {"sentence_interpretation", "completed"} and isinstance(total_parts, (int, float)):
                    return max(0, int(total_parts))
                if phase in {"sentence_interpretation", "completed"} and isinstance(processed_parts, (int, float)):
                    return max(0, int(processed_parts))
        return 0

    def list_ingest_events(self, run_id: str) -> list[IngestEvent]:
        return self._ingest_event_store.list_for_run(run_id)

    def _delete_ingest_item_outputs(self, item: IngestItem) -> None:
        return self._ingest_item_processor._delete_ingest_item_outputs(item)


    @staticmethod
    def _reset_reprocess_item_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        return IngestItemProcessor._reset_reprocess_item_metadata(metadata)


    def request_ingest_item_reprocess(self, item_id: str, *, current_user_id: int | None = None) -> IngestRun:
        return self._ingest_item_processor.request_ingest_item_reprocess(
            item_id,
            current_user_id=current_user_id,
        )


    def _process_single_ingest_item(
        self,
        *,
        started_run: IngestRun,
        item: IngestItem,
        ingest_input: IngestInput | None,
        force_reprocess: bool = False,
    ) -> bool:
        return self._ingest_item_processor.process_single_item(
            started_run=started_run,
            item=item,
            ingest_input=ingest_input,
            force_reprocess=force_reprocess,
        )


    def process_ingest_run(self, run_id: str, *, auto_refresh_semantic_index: bool = True) -> IngestRun:
        return self._ingest_run_processor.process_run(
            run_id,
            auto_refresh_semantic_index=auto_refresh_semantic_index,
        )


    def process_ingest_item(self, item_id: str) -> IngestRun:
        return self._ingest_item_processor.process_item(item_id)


    def _auto_refresh_semantic_block_index_after_ingest(self, run: IngestRun) -> None:
        if run.status not in {"completed", "partial_success"}:
            return
        semantic_blocks = self._load_existing_semantic_blocks(corpus_uuid=run.corpus_uuid, exclude_interpretation_run_id=None)
        if not semantic_blocks:
            return
        metadata = dict(run.metadata or {})
        if metadata.get("semantic_block_auto_index_status") in {"completed", "scheduled"}:
            return
        try:
            build = self.schedule_index_build(
                tenant=run.tenant,
                corpus_uuid=run.corpus_uuid,
                index_profile_key=DEFAULT_INDEX_PROFILE.key,
                created_by=run.created_by,
            )
            metadata.update(
                {
                    "semantic_block_auto_index_status": "scheduled",
                    "index_progress_state": "embedding_queued",
                    "semantic_block_auto_index_build_id": build.id,
                }
            )
            self._ingest_run_store.update(replace(run, metadata=metadata, updated_at=_utcnow()))

            async def _run() -> None:
                try:
                    latest_start = self._ingest_run_store.get(run.id)
                    if latest_start is not None:
                        latest_start_metadata = dict(latest_start.metadata or {})
                        latest_start_metadata["index_progress_state"] = "embedding_started"
                        self._ingest_run_store.update(
                            replace(latest_start, metadata=latest_start_metadata, updated_at=_utcnow())
                        )
                    finished = await self.run_index_build(build.id)
                    latest = self._ingest_run_store.get(run.id)
                    if latest is not None:
                        latest_metadata = dict(latest.metadata or {})
                        latest_metadata.update(
                            {
                                "semantic_block_auto_index_status": finished.status,
                                "semantic_block_auto_index_build_id": finished.id,
                                "index_progress_state": "index_ready" if finished.status == "ready" else "index_failed",
                            }
                        )
                        self._ingest_run_store.update(replace(latest, metadata=latest_metadata, updated_at=_utcnow()))
                except Exception as exc:
                    logger.warning("semantic block auto index task failed: %s", exc, exc_info=True)
                    latest = self._ingest_run_store.get(run.id)
                    if latest is not None:
                        latest_metadata = dict(latest.metadata or {})
                        latest_metadata.update(
                            {
                                "semantic_block_auto_index_status": "failed",
                                "semantic_block_auto_index_error": str(exc),
                                "index_progress_state": "index_failed",
                            }
                        )
                        self._ingest_run_store.update(replace(latest, metadata=latest_metadata, updated_at=_utcnow()))

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(_run())
            else:
                loop.create_task(_run())
        except Exception as exc:
            logger.warning("semantic block auto index refresh failed: %s", exc, exc_info=True)
            latest = self._ingest_run_store.get(run.id)
            if latest is not None:
                latest_metadata = dict(latest.metadata or {})
                latest_metadata.update(
                    {
                        "semantic_block_auto_index_status": "failed",
                        "semantic_block_auto_index_error": str(exc),
                        "index_progress_state": "index_failed",
                    }
                )
                self._ingest_run_store.update(replace(latest, metadata=latest_metadata, updated_at=_utcnow()))

    def update_semantic_block_status(
        self,
        *,
        corpus_uuid: str,
        block_id: str,
        status: str,
        updated_by: int | None = None,
    ) -> dict[str, Any]:
        allowed = {"draft", "approved", "rejected", "withdrawn", "outdated", "disputed"}
        normalized_status = str(status or "").strip().lower()
        if normalized_status not in allowed:
            raise ValueError(f"Invalid semantic block status: {status}")
        if self._interpretation_run_store is None:
            raise ValueError("Interpretation run store is not available")
        list_for_corpus = getattr(self._interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            raise ValueError("Interpretation run listing is not available")
        runs = list_for_corpus(corpus_uuid, limit=50)
        for run in runs:
            metadata = dict(run.metadata or {})
            blocks = list(metadata.get("semantic_blocks") or [])
            changed = False
            updated_block: dict[str, Any] | None = None
            next_blocks: list[dict[str, Any]] = []
            for block in blocks:
                if not isinstance(block, dict):
                    next_blocks.append(block)
                    continue
                if str(block.get("id") or "") != str(block_id):
                    next_blocks.append(block)
                    continue
                updated_block = dict(block)
                block_metadata = dict(updated_block.get("metadata") or {})
                block_metadata["block_status"] = normalized_status
                block_metadata["status_updated_by"] = updated_by
                block_metadata["status_updated_at"] = _utcnow().isoformat()
                updated_block["metadata"] = block_metadata
                updated_block["block_status"] = normalized_status
                changed = True
                next_blocks.append(updated_block)
            if not changed:
                continue
            refreshed_blocks = enrich_semantic_blocks_with_quality(
                [dict(item) for item in next_blocks if isinstance(item, dict)],
                existing_blocks=[],
                source_type=None,
            )
            refreshed_by_id = {str(item.get("id") or ""): item for item in refreshed_blocks}
            metadata["semantic_blocks"] = [refreshed_by_id.get(str(item.get("id") or ""), item) if isinstance(item, dict) else item for item in next_blocks]
            self._interpretation_run_store.update(replace(run, metadata=metadata, updated_at=_utcnow()))
            return {
                "block_id": block_id,
                "status": normalized_status,
                "interpretation_run_id": run.id,
                "block": refreshed_by_id.get(str(block_id), updated_block or {}),
            }
        raise ValueError(f"Semantic block not found: {block_id}")

    def schedule_index_build(self, *, tenant: str, corpus_uuid: str, index_profile_key: str, created_by: int | None) -> IndexBuild:
        return self._index_build_service.schedule_index_build(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            index_profile_key=index_profile_key,
            created_by=created_by,
        )

    def get_index_build(self, build_id: str) -> IndexBuild | None:
        return self._index_build_store.get(build_id)

    def list_index_builds(self, corpus_uuid: str) -> list[IndexBuild]:
        return self._index_build_store.list_for_corpus(corpus_uuid)

    def is_ingest_run_stale(self, run: IngestRun) -> bool:
        if run.status not in {"queued", "processing"}:
            return False
        reference = run.updated_at or run.started_at or run.created_at
        if reference is None:
            return False
        return (_utcnow() - reference).total_seconds() >= self._STALE_INGEST_RUN_FAIL_AFTER_SEC

    def mark_ingest_run_failed_as_stale(self, run_id: str, *, reason: str) -> IngestRun:
        run = self._ingest_run_store.get(run_id)
        if run is None:
            raise ValueError("Ingest run not found")
        if run.status not in {"queued", "processing"}:
            return run
        metadata = dict(run.metadata or {})
        metadata["stale_recovery_status"] = "failed"
        metadata["stale_recovery_reason"] = reason
        metadata["stale_recovery_at"] = _utcnow().isoformat()
        failed = self._ingest_run_store.update(
            replace(
                run,
                status="failed",
                completed_at=_utcnow(),
                updated_at=_utcnow(),
                metadata=metadata,
            )
        )
        self._record_ingest_event(
            run_id=failed.id,
            event_type="run_stale_failed",
            status="failed",
            message=reason,
        )
        return failed

    def mark_ingest_run_enqueue_failed(self, run_id: str, *, reason: str) -> IngestRun:
        run = self._ingest_run_store.get(run_id)
        if run is None:
            raise ValueError("Ingest run not found")
        metadata = dict(run.metadata or {})
        metadata["enqueue_status"] = "failed"
        metadata["enqueue_error"] = reason
        metadata["enqueue_failed_at"] = _utcnow().isoformat()
        failed = self._ingest_run_store.update(
            replace(
                run,
                status="failed",
                queued_count=0,
                processing_count=0,
                failed_count=max(1, int(run.batch_size or 1)),
                completed_at=_utcnow(),
                updated_at=_utcnow(),
                metadata=metadata,
            )
        )
        self._record_ingest_event(
            run_id=failed.id,
            event_type="enqueue_failed",
            status="failed",
            message=reason,
        )
        return failed

    def is_index_build_stale(self, build: IndexBuild) -> bool:
        return self._index_build_service.is_index_build_stale(build)

    def mark_index_build_failed_as_stale(self, build_id: str, *, reason: str) -> IndexBuild:
        return self._index_build_service.mark_index_build_failed_as_stale(build_id, reason=reason)

    async def run_index_build(self, build_id: str) -> IndexBuild:
        return await self._index_build_service.run_index_build(build_id)

    async def run_index_build_with_retry(self, build_id: str) -> IndexBuild:
        return await self._index_build_service.run_index_build_with_retry(build_id)

    def _resolve_builds(self, *, corpus_uuid: str, build_ids: list[str] | None = None) -> list[IndexBuild]:
        def is_ready_build(item: IndexBuild | None) -> bool:
            if item is None:
                return False
            status = str(getattr(item, "status", "") or "").strip().lower()
            if status in {"ready", "completed", "success", "succeeded", "done"}:
                return True
            progress_state = str((getattr(item, "metadata", {}) or {}).get("index_progress_state") or "").strip().lower()
            if progress_state in {"index_ready", "ready", "completed", "done"}:
                return True
            return False

        if build_ids:
            builds = [item for item in (self._index_build_store.get(build_id) for build_id in build_ids) if is_ready_build(item)]
        else:
            builds = [item for item in self._index_build_store.list_for_corpus(corpus_uuid) if is_ready_build(item)]
            builds = builds[:1]
        return [item for item in builds if is_ready_build(item)]

    async def _retrieve_hits_with_resilience(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        builds: list[IndexBuild],
        retrieval_profile: RetrievalProfile,
        query_profile: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return await self._retrieval_service.retrieve_hits_with_resilience(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            builds=builds,
            retrieval_profile=retrieval_profile,
            query_profile=query_profile,
        )

    def apply_knowledge_feedback(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        target_entity: str,
        claim_text: str,
        feedback_type: str,
        optional_new_claim: str | None = None,
        user_input: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        return self._knowledge_feedback_service.apply(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            target_entity=target_entity,
            claim_text=claim_text,
            feedback_type=feedback_type,
            optional_new_claim=optional_new_claim,
            user_input=user_input,
            user_id=user_id,
        )

    def withdraw_source(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        source_id: str,
        user_input: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        return self._knowledge_feedback_service.withdraw_source(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            source_id=source_id,
            user_input=user_input,
            user_id=user_id,
        )

    def get_lineage(
        self,
        *,
        corpus_uuid: str,
        claim_id: str | None = None,
        profile_id: str | None = None,
    ) -> dict[str, Any]:
        return self._lineage_service.get_lineage(
            corpus_uuid=corpus_uuid,
            claim_id=claim_id,
            profile_id=profile_id,
        )

    def get_quality_report(self, *, corpus_uuid: str) -> dict[str, Any]:
        return self._report_service.get_quality_report(corpus_uuid=corpus_uuid)

    async def retrieve(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        build_ids: list[str] | None = None,
        retrieval_profile: RetrievalProfile | None = None,
        context_profile: ContextProfile | None = None,
        compare_mode: bool = False,
    ) -> QueryRun:
        return await self._retrieval_service.retrieve(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            build_ids=build_ids,
            retrieval_profile=retrieval_profile,
            context_profile=context_profile,
            compare_mode=compare_mode,
        )

    async def build_chat_context(
        self,
        *,
        tenant: str | None = None,
        corpus_uuid: str | None = None,
        query: str | None = None,
        build_ids: list[str] | None = None,
        retrieval_profile: RetrievalProfile | None = None,
        context_profile: ContextProfile | None = None,
        question: str | None = None,
        kb_uuid: str | None = None,
        current_user_id: int | None = None,
        current_user_role: str | None = None,
        parsed_query: dict[str, Any] | None = None,
        debug: bool = False,
    ) -> dict[str, Any]:
        return await self._retrieval_service.build_chat_context(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            build_ids=build_ids,
            retrieval_profile=retrieval_profile,
            context_profile=context_profile,
            question=question,
            kb_uuid=kb_uuid,
            current_user_id=current_user_id,
            current_user_role=current_user_role,
            parsed_query=parsed_query,
            debug=debug,
        )

    async def answer_support(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        query: str,
        build_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return await self._retrieval_service.answer_support(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            query=query,
            build_ids=build_ids,
        )

    def get_metrics(self) -> dict[str, object]:
        return self._metrics_store.snapshot()


__all__ = ["KnowledgeFacade"]
