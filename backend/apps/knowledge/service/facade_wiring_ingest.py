from __future__ import annotations

from typing import Any

from apps.knowledge.service.facade_mixin_imports import (
    IngestItemProcessor,
    IngestItemProcessorDependencies,
    IngestProgressService,
    IngestRunCreationDependencies,
    IngestRunCreationService,
    IngestRunProcessor,
    IngestRunProcessorDependencies,
)


def wire_ingest_runtime(owner: Any) -> None:
    owner._ingest_progress_service = IngestProgressService(
        ingest_item_store=owner._ingest_item_store,
        refresh_ingest_run=owner._refresh_ingest_run,
    )
    owner._ingest_item_processor = IngestItemProcessor(
        IngestItemProcessorDependencies(
            object_storage=owner._object_storage,
            url_fetch_service=owner._url_fetch_service,
            source_store=owner._source_store,
            document_store=owner._document_store,
            sentence_store=owner._sentence_store,
            paragraph_store=owner._paragraph_store,
            parser_run_store=owner._parser_run_store,
            space_time_frame_store=owner._space_time_frame_store,
            claim_store=owner._claim_store,
            mention_store=owner._mention_store,
            sentence_interpretation_store=owner._sentence_interpretation_store,
            interpretation_run_store=owner._interpretation_run_store,
            ingest_item_store=owner._ingest_item_store,
            ingest_run_store=owner._ingest_run_store,
            ingest_input_store=owner._ingest_input_store,
            metrics_store=owner._metrics_store,
            parse_source=owner.parse_source,
            normalize_parser_text=owner._normalize_parser_text,
            refresh_ingest_run=owner._refresh_ingest_run,
            is_stale_parser_processing=owner._is_stale_parser_processing,
            record_ingest_event=owner._record_ingest_event,
            load_existing_semantic_blocks=lambda **kwargs: owner._load_existing_semantic_blocks(**kwargs),
            schedule_index_build=lambda **kwargs: owner.schedule_index_build(**kwargs),
            run_index_build=lambda build_id: owner.run_index_build(build_id),
            ingest_runs=owner._ingest_runs,
            auto_refresh_semantic_block_index_after_ingest=owner._auto_refresh_semantic_block_index_after_ingest,
            log_ingest_trace_summary=owner._log_ingest_trace_summary,
            sha256_text=owner._sha256_text,
            sha256_bytes=owner._sha256_bytes,
            ingest_idempotency_key=owner._ingest_idempotency_key,
            log_step=owner._log_step,
            truncate_error_message=owner._truncate_error_message,
            parser_error_message_max=owner._PARSER_ERROR_MESSAGE_MAX,
            stale_parser_restart_after_sec=owner._STALE_PARSER_RESTART_AFTER_SEC,
        ),
        progress_service=owner._ingest_progress_service,
    )
    owner._ingest_run_processor = IngestRunProcessor(
        IngestRunProcessorDependencies(
            ingest_run_store=owner._ingest_run_store,
            ingest_item_store=owner._ingest_item_store,
            ingest_input_store=owner._ingest_input_store,
            ingest_runs=owner._ingest_runs,
            auto_refresh_semantic_block_index_after_ingest=owner._auto_refresh_semantic_block_index_after_ingest,
            log_ingest_trace_summary=owner._log_ingest_trace_summary,
        ),
        item_processor=owner._ingest_item_processor,
    )
    owner._ingest_run_creation_service = IngestRunCreationService(
        IngestRunCreationDependencies(
            knowledge_audit_service=owner._knowledge_audit_service,
            ingest_item_store=owner._ingest_item_store,
            ingest_input_store=owner._ingest_input_store,
            source_storage_service=owner._source_storage_service,
            url_fetch_service=owner._url_fetch_service,
            require_corpus=owner._require_corpus,
            ingest_runs=owner._ingest_runs,
            ensure_title=owner._ensure_title,
            refresh_ingest_run=owner._refresh_ingest_run,
            log_step=owner._log_step,
        ),
        progress_service=owner._ingest_progress_service,
    )


__all__ = ["wire_ingest_runtime"]
