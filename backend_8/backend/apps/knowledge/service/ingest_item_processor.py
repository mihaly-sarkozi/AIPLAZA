# backend/apps/knowledge/service/ingest_item_processor.py
# Owns ingest item processing and reprocess orchestration extracted from KnowledgeFacade.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
import logging
from typing import Any

from apps.knowledge.errors import (
    IngestItemNotFound,
    IngestRunNotFound,
)
from apps.knowledge.domain.ingest_input import IngestInput
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.domain.source import Source
from apps.knowledge.service.facade_helpers import utcnow as _utcnow
from apps.knowledge.service.ingest_item_reprocess_service import IngestItemReprocessService
from apps.knowledge.service.ingest_duplicate_service import IngestDuplicateService
from apps.knowledge.service.ingest_input_validation_service import IngestInputValidationService
from apps.knowledge.service.ingest_item_completion_service import IngestItemCompletionService
from apps.knowledge.service.ingest_item_failure_service import IngestItemFailureService
from apps.knowledge.service.ingest_pipeline_progress_service import IngestPipelineProgressService
from apps.knowledge.service.ingest_progress_service import IngestProgressService
from apps.knowledge.service.ingest_source_factory import IngestSourceFactory
from apps.knowledge.service.ingest_source_parser import IngestSourceParser
from apps.knowledge.service.knowledge_cleanup_service import KnowledgeCleanupService
from apps.knowledge.service.parse_output_cleanup_service import ParseOutputCleanupService
from apps.knowledge.service.semantic_index_refresh_service import SemanticIndexRefreshService
from core.kernel.interface.observability import (
    observability_scope,
)
from shared.documents import ExtractedDocument

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestItemProcessorDependencies:
    object_storage: Any
    url_fetch_service: Any
    source_store: Any
    document_store: Any
    sentence_store: Any
    paragraph_store: Any
    parser_run_store: Any
    space_time_frame_store: Any
    claim_store: Any
    mention_store: Any
    sentence_interpretation_store: Any
    interpretation_run_store: Any
    ingest_item_store: Any
    ingest_run_store: Any
    ingest_input_store: Any
    metrics_store: Any
    parse_source: Callable[..., Any]
    normalize_parser_text: Callable[..., str]
    refresh_ingest_run: Callable[[str], IngestRun]
    is_stale_parser_processing: Callable[..., bool]
    record_ingest_event: Callable[..., Any]
    load_existing_semantic_blocks: Callable[..., list[dict[str, Any]]]
    schedule_index_build: Callable[..., Any]
    run_index_build: Callable[..., Any]
    ingest_runs: Callable[[], Any]
    auto_refresh_semantic_block_index_after_ingest: Callable[[IngestRun], None]
    log_ingest_trace_summary: Callable[[str], None]
    sha256_text: Callable[[str], str]
    sha256_bytes: Callable[[bytes], str]
    ingest_idempotency_key: Callable[..., str]
    log_step: Callable[..., None]
    truncate_error_message: Callable[..., str]
    parser_error_message_max: int
    stale_parser_restart_after_sec: int


class IngestItemProcessor:
    def __init__(self, dependencies: IngestItemProcessorDependencies, *, progress_service: IngestProgressService) -> None:
        self._progress_service = progress_service
        self._object_storage = dependencies.object_storage
        self._url_fetch_service = dependencies.url_fetch_service
        self._source_store = dependencies.source_store
        self._document_store = dependencies.document_store
        self._sentence_store = dependencies.sentence_store
        self._paragraph_store = dependencies.paragraph_store
        self._parser_run_store = dependencies.parser_run_store
        self._space_time_frame_store = dependencies.space_time_frame_store
        self._claim_store = dependencies.claim_store
        self._mention_store = dependencies.mention_store
        self._sentence_interpretation_store = dependencies.sentence_interpretation_store
        self._interpretation_run_store = dependencies.interpretation_run_store
        self._ingest_item_store = dependencies.ingest_item_store
        self._ingest_run_store = dependencies.ingest_run_store
        self._ingest_input_store = dependencies.ingest_input_store
        self._metrics_store = dependencies.metrics_store
        self._parse_source = dependencies.parse_source
        self._normalize_parser_text = dependencies.normalize_parser_text
        self._refresh_ingest_run = dependencies.refresh_ingest_run
        self._is_stale_parser_processing_callback = dependencies.is_stale_parser_processing
        self._record_ingest_event = dependencies.record_ingest_event
        self._load_existing_semantic_blocks = dependencies.load_existing_semantic_blocks
        self._ingest_runs = dependencies.ingest_runs
        self._auto_refresh_semantic_block_index_after_ingest = dependencies.auto_refresh_semantic_block_index_after_ingest
        self._log_ingest_trace_summary = dependencies.log_ingest_trace_summary
        self._sha256_text = dependencies.sha256_text
        self._sha256_bytes = dependencies.sha256_bytes
        self._ingest_idempotency_key = dependencies.ingest_idempotency_key
        self._log_step = dependencies.log_step
        self._truncate_error_message = dependencies.truncate_error_message
        self._PARSER_ERROR_MESSAGE_MAX = dependencies.parser_error_message_max
        self._STALE_PARSER_RESTART_AFTER_SEC = dependencies.stale_parser_restart_after_sec
        self._source_parser = IngestSourceParser(
            object_storage=self._object_storage,
            url_fetch_service=self._url_fetch_service,
            normalize_parser_text=self._normalize_parser_text,
            estimate_file_character_count_from_size=self._estimate_file_character_count_from_size,
        )
        self._source_factory = IngestSourceFactory(source_store=self._source_store)
        self._cleanup_service = ParseOutputCleanupService(
            document_store=self._document_store,
            sentence_store=self._sentence_store,
            paragraph_store=self._paragraph_store,
            parser_run_store=self._parser_run_store,
            source_store=self._source_store,
            space_time_frame_store=self._space_time_frame_store,
            claim_store=self._claim_store,
            mention_store=self._mention_store,
            sentence_interpretation_store=self._sentence_interpretation_store,
            interpretation_run_store=self._interpretation_run_store,
        )
        self._reprocess_service = IngestItemReprocessService(
            ingest_item_store=self._ingest_item_store,
            ingest_run_store=self._ingest_run_store,
            cleanup_service=self._cleanup_service,
            refresh_ingest_run=self._refresh_ingest_run,
            is_stale_parser_processing=self._is_stale_parser_processing_callback,
            record_ingest_event=self._record_ingest_event,
        )
        self._auto_index_service = SemanticIndexRefreshService(
            ingest_run_store=lambda: self._ingest_run_store,
            load_existing_semantic_blocks=self._load_existing_semantic_blocks,
            schedule_index_build=dependencies.schedule_index_build,
            run_index_build=dependencies.run_index_build,
        )
        self._pipeline_progress_service = IngestPipelineProgressService(progress_service=progress_service)
        self._input_validation_service = IngestInputValidationService(
            object_storage=self._object_storage,
            url_fetch_service=self._url_fetch_service,
            ingest_item_store=self._ingest_item_store,
            sha256_text=self._sha256_text,
            sha256_bytes=self._sha256_bytes,
        )
        self._duplicate_service = IngestDuplicateService(
            ingest_item_store=self._ingest_item_store,
            progress_service=progress_service,
            ingest_idempotency_key=self._ingest_idempotency_key,
            record_ingest_event=self._record_ingest_event,
        )
        self._completion_service = IngestItemCompletionService(
            ingest_item_store=self._ingest_item_store,
            document_store=self._document_store,
            sentence_store=self._sentence_store,
            progress_service=progress_service,
            ingest_idempotency_key=self._ingest_idempotency_key,
            record_ingest_event=self._record_ingest_event,
        )
        self._failure_service = IngestItemFailureService(
            ingest_runs=self._ingest_runs,
            progress_service=progress_service,
            record_ingest_event=self._record_ingest_event,
            metrics_store=self._metrics_store,
            log_step=self._log_step,
            truncate_error_message=self._truncate_error_message,
            parser_error_message_max=self._PARSER_ERROR_MESSAGE_MAX,
        )

    def _estimate_file_character_count_from_size(self, size_bytes: int | None) -> int:
        return self._progress_service.estimate_file_character_count_from_size(size_bytes)

    def _format_size_label(self, size_bytes: int | None) -> str:
        return self._progress_service.format_size_label(size_bytes)

    def _build_processing_module(self, **kwargs: Any) -> dict[str, Any]:
        return self._progress_service.build_processing_module(**kwargs)

    def _build_document_progress(self, **kwargs: Any) -> dict[str, Any]:
        return self._progress_service.build_document_progress(**kwargs)

    def _update_item_processing_summary(self, item: IngestItem, **kwargs: Any) -> IngestItem:
        return self._progress_service.update_item_processing_summary(item, **kwargs)

    def _delete_for_document_if_table_exists(self, store: Any, document_id: str, *, table_name: str) -> int:
        return KnowledgeCleanupService.delete_for_document_if_table_exists(store, document_id, table_name=table_name)

    def process_item(
        self,
        item_id: str,
    ) -> IngestRun:
        item = self._ingest_item_store.get(item_id)
        if item is None:
            raise IngestItemNotFound()
        run = self._ingest_run_store.get(item.ingest_run_id)
        if run is None:
            raise IngestRunNotFound()
        started_run = self._ingest_runs().mark_run_processing(run)
        with observability_scope(ingest_run_id=run.id, ingest_item_id=item.id, corpus_uuid=run.corpus_uuid):
            try:
                self.process_single_item(
                    started_run=started_run,
                    item=item,
                    ingest_input=self._ingest_input_store.get_for_item(item.id),
                    force_reprocess=True,
                )
            finally:
                self._ingest_runs().recalculate_progress(run.id)
        final_run = self._ingest_runs().mark_run_completed_if_ready(run.id)
        self._auto_refresh_semantic_block_index_after_ingest(final_run)
        final_run = self._ingest_runs().mark_run_completed_if_ready(run.id)
        self._log_ingest_trace_summary(run.id)
        return final_run

    def process_single_item(
        self,
        *,
        started_run: IngestRun,
        item: IngestItem,
        ingest_input: IngestInput | None,
        force_reprocess: bool = False,
    ) -> bool:
        return self._process_single_ingest_item(
            started_run=started_run,
            item=item,
            ingest_input=ingest_input,
            force_reprocess=force_reprocess,
        )

    def auto_refresh_semantic_block_index_after_ingest(self, run: IngestRun) -> None:
        self._auto_index_service.refresh_after_ingest(run)

    def _extract_parser_document_from_source(
        self,
        source: Source,
        *,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> ExtractedDocument:
        return self._source_parser.extract_document(source, progress_callback=progress_callback)

    def parse_source(
        self,
        source_id: str,
        *,
        created_by: int | None = None,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> Any:
        return self._parse_source(
            source_id,
            created_by=created_by,
            progress_callback=progress_callback,
        )

    def _delete_source_parse_outputs(self, source_id: str) -> None:
        self._cleanup_service.delete_source_parse_outputs(source_id)

    def _is_stale_parser_processing(self, source_id: str, *, updated_at: datetime | None = None) -> bool:
        document = self._document_store.get_for_source(source_id)
        parser_run = self._parser_run_store.get_for_source(source_id)
        if document is None or parser_run is None or parser_run.status != "processing":
            return False
        reference_time = updated_at or parser_run.updated_at or document.updated_at
        return (_utcnow() - reference_time).total_seconds() >= self._STALE_PARSER_RESTART_AFTER_SEC

    def is_ingest_item_stale_processing(self, item: IngestItem) -> bool:
        if item.status != "processing":
            return False
        source_id = str(item.source_id or (item.metadata or {}).get("source_id") or "").strip()
        return bool(source_id) and self._is_stale_parser_processing(source_id, updated_at=item.updated_at)

    def _refresh_ingest_run(self, run_id: str) -> IngestRun:
        return self._ingest_runs().recalculate_progress(run_id)

    def _create_source_from_ingest_item(
        self,
        *,
        tenant: str,
        item: IngestItem,
        ingest_input: IngestInput,
        content_hash: str,
        created_by: int | None,
    ) -> Source:
        return self._source_factory.create_source(
            tenant=tenant,
            item=item,
            ingest_input=ingest_input,
            content_hash=content_hash,
            created_by=created_by,
        )

    def _delete_ingest_item_outputs(self, item: IngestItem) -> None:
        self._cleanup_service.delete_ingest_item_outputs(item)

    @staticmethod
    def _reset_reprocess_item_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        return IngestItemReprocessService.reset_reprocess_item_metadata(metadata)

    def request_ingest_item_reprocess(self, item_id: str, *, current_user_id: int | None = None) -> IngestRun:
        return self._reprocess_service.request_reprocess(item_id, current_user_id=current_user_id)

    def _process_single_ingest_item(
        self,
        *,
        started_run: IngestRun,
        item: IngestItem,
        ingest_input: IngestInput | None,
        force_reprocess: bool = False,
    ) -> bool:
        run_id = started_run.id
        if ingest_input is None:
            return self._failure_service.mark_missing_input(run=started_run, item=item)

        current_item = self._ingest_runs().mark_item_processing(
            item,
            progress_message="Validáció és route-előkészítés folyamatban.",
            lease_owner="outbox-worker",
            lease_minutes=15,
        )
        current_item = self._update_item_processing_summary(
            current_item,
            module_updates={
                "parser": self._build_processing_module(
                    key="parser",
                    status="queued",
                    label="Mondatkinyerés",
                    message="A parser modul még nem indult el.",
                ),
                "sentence_interpretation": self._build_processing_module(
                    key="sentence_interpretation",
                    status="queued",
                    label="Mondatértelmezés",
                    message="Az értelmező modul még nem indult el.",
                ),
                "sentence_evaluation": self._build_processing_module(
                    key="sentence_evaluation",
                    status="queued",
                    label="Mondatértékelés",
                    message="Az értékelő rész még nem indult el.",
                ),
            },
            document_progress=self._build_document_progress(
                phase="parser",
                processed_parts=0,
                total_parts=None,
                label="A dokumentum előkészítése még nem indult el.",
            ),
        )
        self._refresh_ingest_run(run_id)
        try:
            content_hash, current_item = self._input_validation_service.prepare_content_hash(current_item, ingest_input)

            duplicate = self._duplicate_service.find_duplicate(
                current_item,
                content_hash=content_hash,
                force_reprocess=force_reprocess,
            )
            if duplicate is not None:
                finished_item = self._duplicate_service.mark_duplicate(
                    run_id=run_id,
                    item=current_item,
                    duplicate=duplicate,
                    content_hash=content_hash,
                )
            else:
                created_source = self._create_source_from_ingest_item(
                    tenant=started_run.tenant,
                    item=current_item,
                    ingest_input=ingest_input,
                    content_hash=content_hash,
                    created_by=current_item.created_by,
                )
                finished_item = self._completion_service.mark_parser_handoff(
                    run_id=run_id,
                    item=current_item,
                    source=created_source,
                    content_hash=content_hash,
                )

                pipeline_progress = self._pipeline_progress_service.callback_for(finished_item)

                parser_run = self.parse_source(
                    created_source.id,
                    created_by=current_item.created_by,
                    progress_callback=pipeline_progress,
                )
                finished_item = self._pipeline_progress_service.current_item
                finished_item = self._completion_service.mark_completed(
                    item=finished_item,
                    source_id=created_source.id,
                    parser_run=parser_run,
                )
            self._record_ingest_event(
                run_id=run_id,
                item_id=current_item.id,
                event_type="validation_passed",
                status="ok",
                message="Az input validációja sikeres.",
                content_hash=content_hash,
                force_reprocess=force_reprocess,
            )
            self._metrics_store.increment("ingest_item_success_count", 1)
            self._log_step(
                "ingest.item.complete",
                status="ok",
                tenant=started_run.tenant,
                ingest_run_id=run_id,
                ingest_item_id=finished_item.id,
            )
            return True
        except Exception as exc:
            return self._failure_service.mark_processing_failed(
                run=started_run,
                item=current_item,
                exc=exc,
                force_reprocess=force_reprocess,
            )

__all__ = ["IngestItemProcessor", "IngestItemProcessorDependencies"]
