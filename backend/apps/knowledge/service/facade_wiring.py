from __future__ import annotations

from typing import Any

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403
from apps.knowledge.service.facade_runtime import KnowledgeFacadeRuntime
from apps.knowledge.service.facade_wiring_ingest import wire_ingest_runtime
from apps.knowledge.service.ingest_listing_service import IngestListingService
from apps.knowledge.service.local_entity_cluster_service import LocalEntityClusterService
from apps.knowledge.service.semantic_block_status_service import SemanticBlockStatusService


class _KnowledgeFacadeWiringHost:
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


def build_knowledge_facade_runtime(owner: Any, **dependencies: Any) -> KnowledgeFacadeRuntime:
    for key, value in dependencies.items():
        setattr(owner, f"_{key}", value)
    owner._mention_extractor = MentionExtractor()
    owner._claim_quality_gate = ClaimQualityGate()
    owner._claim_extractor_v1 = ClaimExtractorV1(quality_gate=owner._claim_quality_gate)
    owner._space_time_extractor_v1 = SpaceTimeExtractorV1()
    owner._local_resolver_v1 = LocalResolverV1()
    owner._knowledge_cleanup_service = KnowledgeCleanupService(
        KnowledgeCleanupDependencies(
            corpus_store=owner._corpus_store,
            ingest_input_store=owner._ingest_input_store,
            index_build_store=owner._index_build_store,
            object_storage=owner._object_storage,
            vector_index_factory=owner._vector_index_factory,
            ingest_event_store=owner._ingest_event_store,
            ingest_item_store=owner._ingest_item_store,
            ingest_run_store=owner._ingest_run_store,
            sentence_store=owner._sentence_store,
            paragraph_store=owner._paragraph_store,
            document_store=owner._document_store,
            parser_run_store=owner._parser_run_store,
            claim_store=owner._claim_store,
            space_time_frame_store=owner._space_time_frame_store,
            mention_store=owner._mention_store,
            sentence_interpretation_store=owner._sentence_interpretation_store,
            interpretation_run_store=owner._interpretation_run_store,
            query_run_store=owner._query_run_store,
            source_store=owner._source_store,
            log_step=owner._log_step,
        )
    )
    owner._mention_resolution_service = MentionResolutionService(mention_extractor=owner._mention_extractor)
    owner._local_entity_cluster_service = LocalEntityClusterService(
        resolver=owner._local_resolver_v1,
        repository=owner._local_entity_cluster_repository,
        is_missing_table_error=owner._knowledge_cleanup_service.is_missing_table_error,
    )
    owner._information_value_scorer = InformationValueScorer()
    owner._claim_payload_builder = ClaimPayloadBuilder(
        claim_extractor=owner._claim_extractor_v1,
        quality_gate=owner._claim_quality_gate,
        information_value_scorer=owner._information_value_scorer,
        resolve_sentence_language=owner._resolve_sentence_language,
        build_sentence_mentions=owner._build_sentence_mentions,
        build_space_time_frames_for_claims=owner._build_space_time_frames_for_claims,
        is_claim_debug_enabled=owner._is_claim_debug_enabled,
    )
    owner._sentence_unit_builder = SentenceUnitBuilder(
        claim_fine_splitter=owner._claim_fine_splitter,
        information_value_scorer=owner._information_value_scorer,
        enable_claim_fine_split_during_parsing=owner._ENABLE_CLAIM_FINE_SPLIT_DURING_PARSING,
    )
    owner._document_interpretation_service = DocumentInterpretationService(
        interpretation_run_store=owner._interpretation_run_store,
        sentence_interpretation_store=owner._sentence_interpretation_store,
        mention_store=owner._mention_store,
        claim_store=owner._claim_store,
        space_time_frame_store=owner._space_time_frame_store,
        build_sentence_mentions=owner._build_sentence_mentions,
        resolve_sentence_language=owner._resolve_sentence_language,
        build_sentence_claim_payload=owner._build_sentence_claim_payload,
        finalize_sentence_after_subject_context=owner._finalize_sentence_after_subject_context,
        resolve_and_persist_local_entity_clusters=owner._resolve_and_persist_local_entity_clusters,
        load_existing_semantic_blocks=owner._load_existing_semantic_blocks,
        load_existing_search_profiles=owner._load_existing_search_profiles,
        load_existing_global_profiles=owner._load_existing_global_profiles,
        is_missing_table_error=owner._knowledge_cleanup_service.is_missing_table_error,
        truncate_error_message=owner._truncate_error_message,
        interpretation_error_message_max=owner._INTERPRETATION_ERROR_MESSAGE_MAX,
    )
    owner._trace_service = KnowledgeTraceService(
        ingest_run_store=owner._ingest_run_store,
        ingest_item_store=owner._ingest_item_store,
        source_store=owner._source_store,
        document_store=owner._document_store,
        sentence_store=owner._sentence_store,
        mention_store=owner._mention_store,
        claim_store=owner._claim_store,
        space_time_frame_store=owner._space_time_frame_store,
        interpretation_run_store=owner._interpretation_run_store,
        local_entity_cluster_repository=owner._local_entity_cluster_repository,
    )
    owner._ingest_listing_service = IngestListingService(
        ingest_run_store=lambda: owner._ingest_run_store,
        ingest_item_store=lambda: owner._ingest_item_store,
        document_store=lambda: owner._document_store,
        refresh_ingest_run=lambda run_id: owner._refresh_ingest_run(run_id),
        list_ingest_items=lambda run_id: owner.list_ingest_items(run_id),
    )
    owner._semantic_block_status_service = SemanticBlockStatusService(
        interpretation_run_store=owner._interpretation_run_store,
    )
    return _finish_runtime(owner)


def _finish_runtime(owner: Any) -> KnowledgeFacadeRuntime:
    owner._chunking_service = ChunkingService(chunk_builder=owner._chunk_builder)
    owner._source_storage_service = owner._source_storage_service or SourceStorageService(owner._object_storage)
    owner._knowledge_audit_service = KnowledgeAuditService(ingest_event_store=owner._ingest_event_store)
    owner._knowledge_feedback_service = KnowledgeFeedbackService(
        source_store=owner._source_store,
        load_existing_global_profiles=lambda **kwargs: owner._load_existing_global_profiles(**kwargs),
        log_step=owner._log_step,
    )
    owner._lineage_service = KnowledgeLineageService(
        KnowledgeLineageDependencies(
            sentence_store=owner._sentence_store,
            knowledge_feedback_service=owner._knowledge_feedback_service,
            load_existing_global_profiles=lambda **kwargs: owner._load_existing_global_profiles(**kwargs),
            load_existing_retrieval_chunks=lambda **kwargs: owner._load_existing_retrieval_chunks(**kwargs),
        )
    )
    owner._report_service = KnowledgeReportService(
        KnowledgeReportDependencies(
            knowledge_feedback_service=owner._knowledge_feedback_service,
            load_existing_global_profiles=lambda **kwargs: owner._load_existing_global_profiles(**kwargs),
        )
    )
    owner._source_access_service = SourceAccessService(
        source_store=owner._source_store,
        document_store=owner._document_store,
        query_run_store=owner._query_run_store,
        ingest_input_store=owner._ingest_input_store,
        object_storage=owner._object_storage,
        user_repo=owner._user_repo,
    )
    owner._profile_history_service = ProfileHistoryService(
        interpretation_run_store=lambda: owner._interpretation_run_store,
        is_missing_table_error=owner._knowledge_cleanup_service.is_missing_table_error,
    )
    owner._index_profile_support = IndexProfileSupport(index_profile_store=owner._index_profile_store)
    owner._corpus_management_service = CorpusManagementService(
        corpus_store=owner._corpus_store,
        metrics_store=owner._metrics_store,
        ingest_input_store=owner._ingest_input_store,
        index_build_store=owner._index_build_store,
        vector_index_factory=owner._vector_index_factory,
        ingest_run_list_summary=owner.ingest_run_list_summary,
        clear_contents=owner.clear_contents,
        log_step=owner._log_step,
        audit_service=getattr(owner, "_audit_service", None),
    )
    owner._knowledge_pii_service = KnowledgePiiService.from_corpus_store(owner._corpus_store)
    owner._url_fetch_service = UrlFetchService(text_normalizer=owner._normalize_parser_text)
    _wire_permissions_and_index(owner)
    _wire_retrieval_parser_and_ingest(owner)
    return KnowledgeFacadeRuntime.from_owner(owner)


def _wire_permissions_and_index(owner: Any) -> None:
    owner._knowledge_permission_service = KnowledgePermissionService(
        corpus_store=owner._corpus_store,
        user_repo_list_all=owner._user_repo_list_all,
        corpus_mapper=owner._to_corpus,
        list_all_unfiltered=owner.list_all_unfiltered,
        audit_service=getattr(owner, "_audit_service", None),
    )
    owner._index_build_service = IndexBuildService(
        corpus_store=owner._corpus_store,
        source_store=owner._source_store,
        index_build_store=owner._index_build_store,
        metrics_store=owner._metrics_store,
        vector_index_factory=owner._vector_index_factory,
        chunking_service=owner._chunking_service,
        default_index_profile=owner._default_index_profile,
        vector_size_for_profile=owner._vector_size_for_profile,
        load_existing_retrieval_chunks=lambda **kwargs: owner._load_existing_retrieval_chunks(**kwargs),
        load_existing_semantic_blocks=lambda **kwargs: owner._load_existing_semantic_blocks(**kwargs),
        log_step=owner._log_step,
        index_build_lock=owner._index_build_lock,
        retry_count=owner._INDEX_BUILD_RETRY_COUNT,
        retry_backoff_sec=owner._INDEX_BUILD_RETRY_BACKOFF_SEC,
        stale_after_sec=owner._STALE_INDEX_BUILD_FAIL_AFTER_SEC,
    )


def _wire_retrieval_parser_and_ingest(owner: Any) -> None:
    owner._retrieval_service = RetrievalService(
        source_store=owner._source_store,
        document_store=owner._document_store,
        corpus_store=owner._corpus_store,
        source_display_type=owner._source_access_service.source_display_type,
        source_created_by_label=owner._source_access_service.source_created_by_label,
        retrieve_query=lambda **kwargs: owner._retrieval_service.retrieve_query_run(**kwargs),
        dependencies=RetrievalServiceDependencies(
            retrieval_engine=owner._retrieval_engine,
            metrics_store=owner._metrics_store,
            index_build_store=owner._index_build_store,
            query_run_store=owner._query_run_store,
            context_builder=owner._context_builder,
            knowledge_feedback_service=owner._knowledge_feedback_service,
            lineage_service=owner._lineage_service,
            load_existing_global_profiles=lambda **kwargs: owner._load_existing_global_profiles(**kwargs),
            load_existing_retrieval_chunks=lambda **kwargs: owner._load_existing_retrieval_chunks(**kwargs),
            load_existing_semantic_blocks=lambda **kwargs: owner._load_existing_semantic_blocks(**kwargs),
            order_chunks_by_vector_hits=lambda chunks, hits: owner._order_chunks_by_vector_hits(chunks, hits),
            semantic_blocks_from_vector_hits=lambda hits: owner._semantic_blocks_from_vector_hits(hits),
            select_semantic_blocks_for_query=lambda *args, **kwargs: owner._select_semantic_blocks_for_query(*args, **kwargs),
            filter_relevant_semantic_blocks=lambda *args, **kwargs: owner._filter_relevant_semantic_blocks(*args, **kwargs),
            semantic_blocks_context=lambda *args, **kwargs: owner._semantic_blocks_context(*args, **kwargs),
            log_step=owner._log_step,
        ),
    )
    owner._parser_orchestrator = ParserOrchestrator(
        source_store=owner._source_store,
        parser_run_store=owner._parser_run_store,
        document_store=owner._document_store,
        paragraph_store=owner._paragraph_store,
        sentence_store=owner._sentence_store,
        extract_parser_document_from_source=owner._extract_parser_document_from_source,
        delete_source_parse_outputs=owner._delete_source_parse_outputs,
        normalize_parser_text=owner._normalize_parser_text,
        describe_empty_extraction=owner._describe_empty_extraction,
        split_paragraphs=owner._split_paragraphs,
        build_claim_refinement_budget=owner._build_claim_refinement_budget,
        build_sentence_units_for_paragraph_with_diagnostics=owner._build_sentence_units_for_paragraph_with_diagnostics,
        interpret_document=owner._interpret_document,
        truncate_error_message=owner._truncate_error_message,
        log_step=owner._log_step,
        parser_error_message_max=owner._PARSER_ERROR_MESSAGE_MAX,
        claim_fine_split_early_stop_after_blocks=owner._CLAIM_FINE_SPLIT_EARLY_STOP_AFTER_BLOCKS,
        claim_fine_split_min_hit_blocks_to_continue=owner._CLAIM_FINE_SPLIT_MIN_HIT_BLOCKS_TO_CONTINUE,
    )
    wire_ingest_runtime(owner)


__all__ = ["KnowledgeFacadeRuntime", "build_knowledge_facade_runtime"]
