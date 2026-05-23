# backend/apps/knowledge/service/ingest_item_processor.py
# Owns ingest item processing and reprocess orchestration extracted from KnowledgeFacade.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
import logging
import time
from typing import Any

from apps.knowledge.errors import (
    IngestItemNotFound,
    IngestItemReprocessConflict,
    IngestRunNotFound,
    KnowledgeValidationError,
)
from apps.knowledge.domain.ingest_input import IngestInput
from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun
from apps.knowledge.domain.source import Source
from apps.knowledge.service.facade_helpers import normalize_text_payload as _normalize_text_payload
from apps.knowledge.service.facade_helpers import utcnow as _utcnow
from apps.knowledge.service.knowledge_cleanup_service import KnowledgeCleanupService
from apps.knowledge.service.ingest_progress_service import IngestProgressService
from core.kernel.interface.observability import (
    increment_metric as increment_platform_metric,
    observe_metric as observe_platform_metric,
    observability_scope,
)
from shared.documents import ExtractedDocument, ExtractedParagraph, extract_document_from_upload

logger = logging.getLogger(__name__)


class IngestItemProcessor:
    def __init__(self, facade: Any, *, progress_service: IngestProgressService) -> None:
        self._facade = facade
        self._progress_service = progress_service

    def __getattr__(self, name: str) -> Any:
        return getattr(self._facade, name)

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

    def _extract_parser_document_from_source(
        self,
        source: Source,
        *,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> ExtractedDocument:
        if source.source_type == "text":
            text = self._normalize_parser_text(source.raw_content)
            paragraphs = [ExtractedParagraph(text=text)] if text else []
            return ExtractedDocument(
                text_content=text,
                paragraphs=paragraphs,
                metadata={"source_type": source.source_type, "extraction_engine": "manual_text_v1"},
            )
        if source.source_type == "file":
            parse_started = time.perf_counter()
            bucket_name = str(source.metadata.get("bucket_name") or "")
            object_key = str(source.metadata.get("object_key") or "")
            filename = str(source.file_ref or source.title or "upload.txt")
            size_bytes = int(source.metadata.get("size_bytes") or 0)
            estimated_char_count = int(
                source.metadata.get("estimated_char_count")
                or self._estimate_file_character_count_from_size(size_bytes)
            )
            if not bucket_name or not object_key:
                raise KnowledgeValidationError("A fájlforráshoz hiányzik az object storage referencia.")
            if progress_callback is not None:
                progress_callback(
                    "file_character_count_started",
                    {
                        "filename": filename,
                        "size_bytes": size_bytes,
                        "estimated_char_count": estimated_char_count,
                        "processed_bytes": 0,
                    },
                )
            stored = self._object_storage.get_bytes(key=object_key, bucket=bucket_name)
            loaded_size_bytes = len(stored.body)
            if progress_callback is not None:
                progress_callback(
                    "file_bytes_loaded",
                    {
                        "filename": filename,
                        "size_bytes": size_bytes or loaded_size_bytes,
                        "estimated_char_count": estimated_char_count,
                        "processed_bytes": loaded_size_bytes,
                    },
                )
            try:
                extracted = extract_document_from_upload(filename, stored.body)
            except Exception:
                increment_platform_metric("file_parse_failures_total", 1.0, tags={"source_type": "file"})
                raise
            finally:
                observe_platform_metric("file_parse_duration_seconds", time.perf_counter() - parse_started, unit="seconds", tags={"source_type": "file"})
            normalized_text = self._normalize_parser_text(extracted.text_content)
            normalized_paragraphs = [
                replace(paragraph, text=self._normalize_parser_text(paragraph.text))
                for paragraph in extracted.paragraphs
                if self._normalize_parser_text(paragraph.text)
            ]
            if not normalized_paragraphs and normalized_text:
                normalized_paragraphs = [ExtractedParagraph(text=normalized_text)]
            if progress_callback is not None:
                progress_callback(
                    "file_character_count_completed",
                    {
                        "filename": filename,
                        "size_bytes": size_bytes or loaded_size_bytes,
                        "estimated_char_count": estimated_char_count,
                        "char_count": len(normalized_text),
                        "paragraph_count": len(normalized_paragraphs),
                    },
                )
            return ExtractedDocument(
                text_content=normalized_text,
                paragraphs=normalized_paragraphs,
                metadata={
                    **dict(extracted.metadata or {}),
                    "source_type": source.source_type,
                    "filename": filename,
                },
            )
        if source.source_type == "url":
            url = str(source.metadata.get("origin_url") or "")
            if not url:
                raise KnowledgeValidationError("A hivatkozás forráshoz hiányzik az URL.")
            return self._url_fetch_service.fetch_document(url, timeout=20)
        fallback_text = self._normalize_parser_text(source.raw_content)
        return ExtractedDocument(
            text_content=fallback_text,
            paragraphs=[ExtractedParagraph(text=fallback_text)] if fallback_text else [],
            metadata={"source_type": source.source_type, "extraction_engine": "fallback_text_v1"},
        )

    def _delete_source_parse_outputs(self, source_id: str) -> None:
        document = self._document_store.get_for_source(source_id)
        if document is not None:
            if self._space_time_frame_store is not None:
                self._delete_for_document_if_table_exists(
                    self._space_time_frame_store,
                    document.id,
                    table_name="knowledge_space_time_frames",
                )
            if self._claim_store is not None:
                self._delete_for_document_if_table_exists(
                    self._claim_store,
                    document.id,
                    table_name="knowledge_claims",
                )
            if self._mention_store is not None:
                self._delete_for_document_if_table_exists(
                    self._mention_store,
                    document.id,
                    table_name="knowledge_mentions",
                )
            if self._sentence_interpretation_store is not None:
                self._delete_for_document_if_table_exists(
                    self._sentence_interpretation_store,
                    document.id,
                    table_name="knowledge_sentence_interpretations",
                )
            if self._interpretation_run_store is not None:
                self._delete_for_document_if_table_exists(
                    self._interpretation_run_store,
                    document.id,
                    table_name="knowledge_interpretation_runs",
                )
            self._sentence_store.delete_for_document(document.id)
            self._paragraph_store.delete_for_document(document.id)
            self._document_store.delete_for_source(source_id)
        self._parser_run_store.delete_for_source(source_id)

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
        if ingest_input.input_type == "text":
            source = Source(
                tenant=tenant,
                corpus_uuid=item.corpus_uuid,
                title=item.title,
                source_type="text",
                raw_content=ingest_input.text_content,
                file_ref=None,
                status="attached",
                created_by=created_by,
                metadata={
                    "ingest_item_id": item.id,
                    "ingest_run_id": item.ingest_run_id,
                    "content_hash": content_hash,
                    "char_count": len(str(ingest_input.text_content or "")),
                },
            )
            return self._source_store.create(source)
        if ingest_input.input_type == "file":
            source = Source(
                tenant=tenant,
                corpus_uuid=item.corpus_uuid,
                title=item.title,
                source_type="file",
                raw_content=None,
                file_ref=ingest_input.original_filename,
                status="attached",
                created_by=created_by,
                metadata={
                    "ingest_item_id": item.id,
                    "ingest_run_id": item.ingest_run_id,
                    "content_hash": content_hash,
                    "storage_provider": ingest_input.storage_provider,
                    "bucket_name": ingest_input.bucket_name,
                    "object_key": ingest_input.object_key,
                    "mime_type": ingest_input.mime_type,
                    "size_bytes": ingest_input.size_bytes,
                    "estimated_char_count": (
                        ingest_input.metadata.get("estimated_char_count")
                        if isinstance(ingest_input.metadata, dict)
                        else None
                    ),
                    "checksum_sha256": ingest_input.checksum_sha256,
                },
            )
            return self._source_store.create(source)
        if ingest_input.input_type == "url":
            source = Source(
                tenant=tenant,
                corpus_uuid=item.corpus_uuid,
                title=item.title,
                source_type="url",
                raw_content=None,
                file_ref=None,
                status="attached",
                created_by=created_by,
                metadata={
                    "ingest_item_id": item.id,
                    "ingest_run_id": item.ingest_run_id,
                    "content_hash": content_hash,
                    "origin_url": ingest_input.origin_url,
                    "url_status_code": item.metadata.get("url_status_code"),
                    "url_content_type": item.metadata.get("url_content_type"),
                },
            )
            return self._source_store.create(source)
        raise KnowledgeValidationError(f"Unsupported source type for ingest input: {ingest_input.input_type}")

    def _delete_ingest_item_outputs(self, item: IngestItem) -> None:
        source_id = str(item.source_id or item.metadata.get("source_id") or "").strip()
        if not source_id:
            return

        document = self._document_store.get_for_source(source_id)
        if document is not None:
            if self._space_time_frame_store is not None:
                self._delete_for_document_if_table_exists(
                    self._space_time_frame_store,
                    document.id,
                    table_name="knowledge_space_time_frames",
                )
            if self._claim_store is not None:
                self._delete_for_document_if_table_exists(
                    self._claim_store,
                    document.id,
                    table_name="knowledge_claims",
                )
            if self._mention_store is not None:
                self._delete_for_document_if_table_exists(
                    self._mention_store,
                    document.id,
                    table_name="knowledge_mentions",
                )
            if self._sentence_interpretation_store is not None:
                self._delete_for_document_if_table_exists(
                    self._sentence_interpretation_store,
                    document.id,
                    table_name="knowledge_sentence_interpretations",
                )
            if self._interpretation_run_store is not None:
                self._delete_for_document_if_table_exists(
                    self._interpretation_run_store,
                    document.id,
                    table_name="knowledge_interpretation_runs",
                )
            self._sentence_store.delete_for_document(document.id)
            self._paragraph_store.delete_for_document(document.id)
            self._document_store.delete_for_source(source_id)

        self._parser_run_store.delete_for_source(source_id)
        self._source_store.delete(source_id)
        log_structured_event(
            "apps.knowledge.audit",
            "knowledge_source_deleted",
            level=logging.INFO,
            knowledge_base_id=str(item.corpus_uuid or ""),
            ingest_run_id=str(item.ingest_run_id or ""),
            ingest_item_id=str(item.id or ""),
            source_id=source_id,
        )

    @staticmethod
    def _reset_reprocess_item_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        cleaned = dict(metadata)
        for key in (
            "source_id",
            "parser_run_id",
            "document_id",
            "sentence_count",
            "paragraph_count",
            "interpretation_run_id",
            "handoff_target",
        ):
            cleaned.pop(key, None)
        cleaned.pop("processing_summary", None)
        cleaned["reprocess_requested_at"] = _utcnow().isoformat()
        return cleaned

    def request_ingest_item_reprocess(self, item_id: str, *, current_user_id: int | None = None) -> IngestRun:
        item = self._ingest_item_store.get(item_id)
        if item is None:
            raise IngestItemNotFound()
        run = self._ingest_run_store.get(item.ingest_run_id)
        if run is None:
            raise IngestRunNotFound()
        if run.status in {"queued", "processing"}:
            run = self._refresh_ingest_run(run.id)
            item = self._ingest_item_store.get(item_id) or item
        source_id = str(item.source_id or item.metadata.get("source_id") or "").strip()
        stale_parser_processing = bool(source_id) and self._is_stale_parser_processing(source_id, updated_at=item.updated_at)
        if (run.status in {"queued", "processing"} or item.status == "processing") and not stale_parser_processing:
            raise IngestItemReprocessConflict("Az ingest rekord jelenleg feldolgozás alatt áll, ezért most nem indítható újra.")

        self._delete_ingest_item_outputs(item)
        reset_item = self._ingest_item_store.update(
            replace(
                item,
                status="received",
                progress_message="Újrafeldolgozás ütemezve.",
                result_message=None,
                error_code=None,
                error_message=None,
                duplicate_of_item_id=None,
                duplicate_of_source_id=None,
                parser_job_id=None,
                source_id=None,
                content_hash=None,
                idempotency_key=None,
                lease_owner=None,
                lease_expires_at=None,
                heartbeat_at=None,
                retry_count=0,
                dead_letter_reason=None,
                started_at=None,
                completed_at=None,
                updated_at=_utcnow(),
                metadata=self._reset_reprocess_item_metadata(item.metadata),
            )
        )
        self._record_ingest_event(
            run_id=run.id,
            item_id=reset_item.id,
            event_type="reprocess_requested",
            status="ok",
            message="A korábbi forrás törölve lett, az ingest item újrafeldolgozásra vár.",
            created_by=current_user_id,
        )
        return self._refresh_ingest_run(run.id)

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
            failed_item = self._ingest_runs().mark_item_failed(
                item,
                error_code="missing_input",
                error_message="Nem található ingest input rekord.",
                progress_message="Hiányzó input rekord.",
            )
            failed_item = self._update_item_processing_summary(
                failed_item,
                module_updates={
                    "parser": self._build_processing_module(
                        key="parser",
                        status="failed",
                        label="Mondatkinyerés",
                        error_message=failed_item.error_message,
                    ),
                    "sentence_interpretation": self._build_processing_module(
                        key="sentence_interpretation",
                        status="failed",
                        label="Mondatértelmezés",
                        error_message=failed_item.error_message,
                    ),
                    "sentence_evaluation": self._build_processing_module(
                        key="sentence_evaluation",
                        status="failed",
                        label="Mondatértékelés",
                        error_message=failed_item.error_message,
                    ),
                },
            )
            self._record_ingest_event(
                run_id=run_id,
                item_id=item.id,
                event_type="validation_failed",
                status="failed",
                message=failed_item.error_message,
                error_code=failed_item.error_code,
            )
            return bool(started_run.continue_on_error)

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
            if ingest_input.input_type == "text":
                content_hash = self._sha256_text(_normalize_text_payload(ingest_input.text_content))
            elif ingest_input.input_type == "file":
                if not ingest_input.bucket_name or not ingest_input.object_key:
                    raise ValueError("Missing object storage reference for file input")
                content_hash = str(ingest_input.checksum_sha256 or "")
                if not content_hash:
                    stored = self._object_storage.get_bytes(
                        key=ingest_input.object_key,
                        bucket=ingest_input.bucket_name,
                    )
                    content_hash = self._sha256_bytes(stored.body)
            elif ingest_input.input_type == "url":
                if not ingest_input.origin_url:
                    raise ValueError("URL input is missing origin_url")
                response = self._url_fetch_service.request_head(ingest_input.origin_url, timeout=15)
                content_hash = self._sha256_text(ingest_input.origin_url)
                current_item = self._ingest_item_store.update(
                    replace(
                        current_item,
                        progress_message=f"URL elérhető, válasz: {response.status_code}.",
                        updated_at=_utcnow(),
                        metadata={
                            **current_item.metadata,
                            "url_status_code": response.status_code,
                            "url_content_type": response.content_type,
                            "url_final_url": response.final_url,
                        },
                    )
                )
            else:
                raise ValueError(f"Unsupported ingest input type: {ingest_input.input_type}")

            duplicate = None
            if not force_reprocess:
                duplicate = self._ingest_item_store.find_by_hash(
                    corpus_uuid=current_item.corpus_uuid,
                    content_hash=content_hash,
                    exclude_item_id=current_item.id,
                    pipeline_version=current_item.pipeline_version,
                )
            if duplicate is not None:
                finished_item = self._ingest_item_store.update(
                    replace(
                        current_item,
                        status="duplicate",
                        content_hash=content_hash,
                        duplicate_of_item_id=duplicate.id,
                        duplicate_of_source_id=duplicate.source_id,
                        idempotency_key=self._ingest_idempotency_key(
                            corpus_uuid=current_item.corpus_uuid,
                            content_hash=content_hash,
                            pipeline_version=current_item.pipeline_version,
                        ),
                        result_message="Duplikátumként jelölve.",
                        progress_message="Duplikált input, parser nem indul.",
                        lease_owner=None,
                        lease_expires_at=None,
                        heartbeat_at=_utcnow(),
                        completed_at=_utcnow(),
                        updated_at=_utcnow(),
                    )
                )
                finished_item = self._update_item_processing_summary(
                    finished_item,
                    module_updates={
                        "parser": self._build_processing_module(
                            key="parser",
                            status="skipped",
                            label="Mondatkinyerés",
                            message="Duplikátum miatt nem indult parser.",
                        ),
                        "sentence_interpretation": self._build_processing_module(
                            key="sentence_interpretation",
                            status="skipped",
                            label="Mondatértelmezés",
                            message="Duplikátum miatt nem indult értelmezés.",
                        ),
                        "sentence_evaluation": self._build_processing_module(
                            key="sentence_evaluation",
                            status="skipped",
                            label="Mondatértékelés",
                            message="Duplikátum miatt nem indult értékelés.",
                        ),
                    },
                    document_progress=self._build_document_progress(
                        phase="duplicate",
                        processed_parts=0,
                        total_parts=0,
                        label="Duplikátumként jelölve, nincs további feldolgozás.",
                    ),
                )
                self._record_ingest_event(
                    run_id=run_id,
                    item_id=current_item.id,
                    event_type="duplicate_detected",
                    status="ok",
                    message="Duplikált input felismerve.",
                    duplicate_of_item_id=duplicate.id,
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
                finished_item = self._ingest_item_store.update(
                    replace(
                        current_item,
                        status="processing",
                        content_hash=content_hash,
                        idempotency_key=self._ingest_idempotency_key(
                            corpus_uuid=current_item.corpus_uuid,
                            content_hash=content_hash,
                            pipeline_version=current_item.pipeline_version,
                        ),
                        progress_message="Ingest lezárva, parserre vár.",
                        result_message="Sikeresen előkészítve a parser modulhoz.",
                        source_id=created_source.id,
                        completed_at=None,
                        updated_at=_utcnow(),
                        metadata={**current_item.metadata, "handoff_target": "source_parser", "source_id": created_source.id},
                    )
                )
                self._record_ingest_event(
                    run_id=run_id,
                    item_id=current_item.id,
                    event_type="source_created",
                    status="ok",
                    message="Source rekord létrehozva az ingest inputhoz.",
                    source_id=created_source.id,
                    source_type=created_source.source_type,
                )
                self._record_ingest_event(
                    run_id=run_id,
                    item_id=current_item.id,
                    event_type="parser_handover_ready",
                    status="ok",
                    message="Az input készen áll a parser modul számára.",
                    content_hash=content_hash,
                )
                finished_item = self._update_item_processing_summary(
                    finished_item,
                    progress_message="A parser modul megkezdte a dokumentum előkészítését.",
                    module_updates={
                        "parser": self._build_processing_module(
                            key="parser",
                            status="processing",
                            label="Mondatkinyerés",
                            message="A parser modul feldolgozza a dokumentumot.",
                        ),
                    },
                    extra_metadata={"source_id": created_source.id},
                )

                def _pipeline_progress(stage: str, payload: dict[str, Any]) -> None:
                    nonlocal finished_item
                    if stage == "file_character_count_started":
                        size_bytes = int(payload.get("size_bytes") or 0)
                        estimated_char_count = int(payload.get("estimated_char_count") or 0)
                        label = (
                            f"Fájl beolvasása és karakterszám becslése indul "
                            f"({self._format_size_label(size_bytes)}, kb. {estimated_char_count} karakter)."
                        )
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message=label,
                            module_updates={
                                "parser": self._build_processing_module(
                                    key="parser",
                                    status="processing",
                                    label="Mondatkinyerés",
                                    message=label,
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="file_character_count",
                                processed_parts=max(1, int(max(size_bytes, 1) * 0.05)) if size_bytes > 0 else 0,
                                total_parts=max(size_bytes, 1),
                                label=label,
                                extra={
                                    "size_bytes": size_bytes,
                                    "estimated_char_count": estimated_char_count,
                                },
                            ),
                            extra_metadata={
                                "size_bytes": size_bytes,
                                "estimated_char_count": estimated_char_count,
                            },
                        )
                        return
                    if stage == "file_bytes_loaded":
                        size_bytes = int(payload.get("size_bytes") or 0)
                        processed_bytes = int(payload.get("processed_bytes") or 0)
                        estimated_char_count = int(payload.get("estimated_char_count") or 0)
                        label = (
                            f"Fájl beolvasva, szövegkinyerés és karakterszámolás folyamatban "
                            f"({self._format_size_label(size_bytes)}, kb. {estimated_char_count} karakter)."
                        )
                        # A szövegkinyerés nem minden formátumnál mérhető soronként, ezért a fájlméretből becsült köztes állapotot mutatjuk.
                        estimated_processed = max(1, int(max(size_bytes, 1) * 0.7))
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message=label,
                            module_updates={
                                "parser": self._build_processing_module(
                                    key="parser",
                                    status="processing",
                                    label="Mondatkinyerés",
                                    processed_parts=min(estimated_processed, max(size_bytes, 1)),
                                    total_parts=max(size_bytes, 1),
                                    message=label,
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="file_character_count",
                                processed_parts=min(estimated_processed, max(size_bytes, 1)),
                                total_parts=max(size_bytes, 1),
                                label=label,
                                extra={
                                    "size_bytes": size_bytes,
                                    "processed_bytes": processed_bytes,
                                    "estimated_char_count": estimated_char_count,
                                },
                            ),
                        )
                        return
                    if stage == "file_character_count_completed":
                        size_bytes = int(payload.get("size_bytes") or 0)
                        estimated_char_count = int(payload.get("estimated_char_count") or 0)
                        char_count = int(payload.get("char_count") or 0)
                        paragraph_count = int(payload.get("paragraph_count") or 0)
                        label = (
                            f"Karakterszámolás kész: {char_count} karakter "
                            f"({self._format_size_label(size_bytes)}, becslés: {estimated_char_count})."
                        )
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message=label,
                            module_updates={
                                "parser": self._build_processing_module(
                                    key="parser",
                                    status="processing",
                                    label="Mondatkinyerés",
                                    processed_parts=max(size_bytes, 1),
                                    total_parts=max(size_bytes, 1),
                                    message=label,
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="file_character_count",
                                processed_parts=max(size_bytes, 1),
                                total_parts=max(size_bytes, 1),
                                label=label,
                                extra={
                                    "size_bytes": size_bytes,
                                    "estimated_char_count": estimated_char_count,
                                    "char_count": char_count,
                                    "paragraph_count": paragraph_count,
                                },
                            ),
                            extra_metadata={
                                "estimated_char_count": estimated_char_count,
                                "char_count": char_count,
                                "paragraph_count": paragraph_count,
                            },
                        )
                        return
                    if stage == "parser_started":
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message="A parser modul fut, a dokumentum szerkezetét készíti elő.",
                            module_updates={
                                "parser": self._build_processing_module(
                                    key="parser",
                                    status="processing",
                                    label="Mondatkinyerés",
                                    run_id=str(payload.get("parser_run_id") or ""),
                                    message="A parser modul fut.",
                                ),
                            },
                        )
                        return
                    if stage in {"parser_block_started", "parser_block_units_ready", "parser_block_completed"}:
                        block_index = int(payload.get("block_index") or 0)
                        total_blocks = int(payload.get("total_blocks") or 0)
                        block_id = str(payload.get("block_id") or "")
                        block_type = str(payload.get("block_type") or "") or "unknown"
                        current_step = str(payload.get("current_step") or "") or "parser"
                        fine_split_run_blocks = int(payload.get("fine_split_run_blocks") or 0)
                        fine_split_not_run_blocks = int(payload.get("fine_split_not_run_blocks") or 0)
                        parser_message = (
                            f"Blokk {block_index} / {total_blocks} ({block_type}) | "
                            f"ID: {block_id} | lépés: {current_step}"
                        )
                        progress_message = parser_message
                        if stage == "parser_block_units_ready":
                            progress_message = (
                                f"{parser_message} | mondatjelöltek: {int(payload.get('candidate_count') or 0)} | "
                                f"finomvágás futott: {int(payload.get('claim_refinement_attempts') or 0)} jelölten | "
                                f"finomított egységek: {int(payload.get('claim_refinement_units') or 0)}"
                            )
                        elif stage == "parser_block_completed":
                            progress_message = (
                                f"{parser_message} | blokk mondatok: {int(payload.get('sentence_count') or 0)} | "
                                f"finomvágás blokkok: {fine_split_run_blocks} igen / {fine_split_not_run_blocks} nem"
                            )
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message=progress_message,
                            module_updates={
                                "parser": self._build_processing_module(
                                    key="parser",
                                    status="processing",
                                    label="Mondatkinyerés",
                                    processed_parts=int(payload.get("blocks_completed") or 0),
                                    total_parts=total_blocks,
                                    run_id=str(payload.get("parser_run_id") or ""),
                                    message=progress_message,
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="parser",
                                processed_parts=int(payload.get("blocks_completed") or 0),
                                total_parts=total_blocks,
                                label=progress_message,
                            ),
                            extra_metadata={
                                "parser_block_status": {
                                    "block_id": block_id or None,
                                    "block_index": block_index,
                                    "total_blocks": total_blocks,
                                    "block_type": block_type,
                                    "current_step": current_step,
                                    "sentence_count": int(payload.get("sentence_count") or 0),
                                    "sentence_unit_count": int(payload.get("sentence_unit_count") or 0),
                                    "candidate_count": int(payload.get("candidate_count") or 0),
                                    "strong_candidate_count": int(payload.get("strong_candidate_count") or 0),
                                    "weak_candidate_count": int(payload.get("weak_candidate_count") or 0),
                                    "claim_refinement_attempts": int(payload.get("claim_refinement_attempts") or 0),
                                    "claim_refinement_hits": int(payload.get("claim_refinement_hits") or 0),
                                    "claim_refinement_units": int(payload.get("claim_refinement_units") or 0),
                                    "fallback_used": bool(payload.get("fallback_used") or False),
                                },
                                "parser_block_counters": {
                                    "blocks_started": int(payload.get("blocks_started") or 0),
                                    "blocks_completed": int(payload.get("blocks_completed") or 0),
                                    "total_blocks": total_blocks,
                                    "fine_split_run_blocks": fine_split_run_blocks,
                                    "fine_split_not_run_blocks": fine_split_not_run_blocks,
                                },
                            },
                        )
                        return
                    if stage == "parser_completed":
                        sentence_count = int(payload.get("sentence_count") or 0)
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message=f"A parser elkészült, {sentence_count} mondat azonosítva.",
                            module_updates={
                                "parser": self._build_processing_module(
                                    key="parser",
                                    status="completed",
                                    label="Mondatkinyerés",
                                    processed_parts=sentence_count,
                                    total_parts=sentence_count,
                                    run_id=str(payload.get("parser_run_id") or ""),
                                    message="A parser modul elkészült.",
                                ),
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="queued",
                                    label="Mondatértelmezés",
                                    processed_parts=0,
                                    total_parts=sentence_count,
                                    message="A mondatok értelmezése indulásra kész.",
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="queued",
                                    label="Mondatértékelés",
                                    processed_parts=0,
                                    total_parts=sentence_count,
                                    message="A mondatok értékelése indulásra kész.",
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="sentence_interpretation",
                                processed_parts=0,
                                total_parts=sentence_count,
                                label=f"0 / {sentence_count} mondat értelmezve",
                            ),
                            extra_metadata={
                                "parser_run_id": payload.get("parser_run_id"),
                                "document_id": payload.get("document_id"),
                                "char_count": int(payload.get("char_count") or 0),
                                "sentence_count": sentence_count,
                                "paragraph_count": int(payload.get("paragraph_count") or 0),
                                "parser_block_counters": {
                                    "blocks_started": int(payload.get("blocks_started") or 0),
                                    "blocks_completed": int(payload.get("blocks_completed") or 0),
                                    "total_blocks": int(payload.get("total_blocks") or 0),
                                    "fine_split_run_blocks": int(payload.get("fine_split_run_blocks") or 0),
                                    "fine_split_not_run_blocks": int(payload.get("fine_split_not_run_blocks") or 0),
                                },
                            },
                        )
                        return
                    if stage == "parser_failed":
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message="A parser modul hibára futott.",
                            module_updates={
                                "parser": self._build_processing_module(
                                    key="parser",
                                    status="failed",
                                    label="Mondatkinyerés",
                                    run_id=str(payload.get("parser_run_id") or ""),
                                    error_message=str(payload.get("error_message") or ""),
                                ),
                            },
                        )
                        return
                    if stage == "interpretation_started":
                        total_sentences = int(payload.get("total_sentences") or 0)
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message="A mondatok értelmezése és értékelése folyamatban van.",
                            module_updates={
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="processing",
                                    label="Mondatértelmezés",
                                    processed_parts=int(payload.get("processed_sentences") or 0),
                                    total_parts=total_sentences,
                                    run_id=str(payload.get("interpretation_run_id") or ""),
                                    message="A mondatok értelmezése folyamatban van.",
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="processing",
                                    label="Mondatértékelés",
                                    processed_parts=int(payload.get("processed_sentences") or 0),
                                    total_parts=total_sentences,
                                    message="A mondatok információértékének meghatározása folyamatban van.",
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="sentence_interpretation",
                                processed_parts=int(payload.get("processed_sentences") or 0),
                                total_parts=total_sentences,
                                label=f"0 / {total_sentences} mondat kész",
                            ),
                            extra_metadata={"interpretation_run_id": payload.get("interpretation_run_id")},
                        )
                        return
                    if stage == "interpretation_progress":
                        processed_sentences = int(payload.get("processed_sentences") or 0)
                        total_sentences = int(payload.get("total_sentences") or 0)
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message=f"Mondatfeldolgozás: {processed_sentences} / {total_sentences} kész.",
                            module_updates={
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="processing",
                                    label="Mondatértelmezés",
                                    processed_parts=processed_sentences,
                                    total_parts=total_sentences,
                                    run_id=str(payload.get("interpretation_run_id") or ""),
                                    message=f"{processed_sentences} / {total_sentences} mondat értelmezve.",
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="processing",
                                    label="Mondatértékelés",
                                    processed_parts=processed_sentences,
                                    total_parts=total_sentences,
                                    message=f"{processed_sentences} / {total_sentences} mondat értékelve.",
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="sentence_interpretation",
                                processed_parts=processed_sentences,
                                total_parts=total_sentences,
                                label=f"{processed_sentences} / {total_sentences} mondat kész",
                            ),
                        )
                        return
                    if stage == "interpretation_completed":
                        processed_sentences = int(payload.get("processed_sentences") or 0)
                        total_sentences = int(payload.get("total_sentences") or processed_sentences)
                        quality = dict(payload.get("quality") or {})
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message=f"A mondatok értelmezése elkészült ({processed_sentences} / {total_sentences}).",
                            module_updates={
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="completed",
                                    label="Mondatértelmezés",
                                    processed_parts=processed_sentences,
                                    total_parts=total_sentences,
                                    run_id=str(payload.get("interpretation_run_id") or ""),
                                    message="A mondatok értelmezése elkészült.",
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="completed",
                                    label="Mondatértékelés",
                                    processed_parts=processed_sentences,
                                    total_parts=total_sentences,
                                    message="A mondatok információérték-értékelése elkészült.",
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="sentence_interpretation",
                                processed_parts=processed_sentences,
                                total_parts=total_sentences,
                                label=f"{processed_sentences} / {total_sentences} mondat kész",
                            ),
                            extra_metadata={"interpretation_quality": quality},
                        )
                        return
                    if stage == "interpretation_failed":
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message="A mondatértelmezés hibára futott.",
                            module_updates={
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="failed",
                                    label="Mondatértelmezés",
                                    processed_parts=int(payload.get("processed_sentences") or 0),
                                    total_parts=int(payload.get("total_sentences") or 0),
                                    run_id=str(payload.get("interpretation_run_id") or ""),
                                    error_message=str(payload.get("error_message") or ""),
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="failed",
                                    label="Mondatértékelés",
                                    processed_parts=int(payload.get("processed_sentences") or 0),
                                    total_parts=int(payload.get("total_sentences") or 0),
                                    error_message=str(payload.get("error_message") or ""),
                                ),
                            },
                        )
                        return
                    if stage == "interpretation_skipped":
                        total_sentences = int(payload.get("total_sentences") or 0)
                        finished_item = self._update_item_processing_summary(
                            finished_item,
                            progress_message="A mondatértelmezés ebben a környezetben ki lett hagyva.",
                            module_updates={
                                "sentence_interpretation": self._build_processing_module(
                                    key="sentence_interpretation",
                                    status="skipped",
                                    label="Mondatértelmezés",
                                    processed_parts=0,
                                    total_parts=total_sentences,
                                    message=str(payload.get("reason") or "A modul nem elérhető."),
                                ),
                                "sentence_evaluation": self._build_processing_module(
                                    key="sentence_evaluation",
                                    status="skipped",
                                    label="Mondatértékelés",
                                    processed_parts=0,
                                    total_parts=total_sentences,
                                    message=str(payload.get("reason") or "A modul nem elérhető."),
                                ),
                            },
                            document_progress=self._build_document_progress(
                                phase="parser",
                                processed_parts=total_sentences,
                                total_parts=total_sentences,
                                label="A parser elkészült, az értelmezés ki lett hagyva.",
                            ),
                        )

                parser_run = self.parse_source(
                    created_source.id,
                    created_by=current_item.created_by,
                    progress_callback=_pipeline_progress,
                )
                parsed_document = self._document_store.get_for_source(created_source.id)
                sentence_count = 0
                char_count = 0
                if parsed_document is not None:
                    char_count = int(parsed_document.char_count or len(parsed_document.text_content or ""))
                    sentence_count = len(self._sentence_store.list_for_document(parsed_document.id))
                finished_item = self._update_item_processing_summary(
                    finished_item,
                    progress_message="A dokumentum feldolgozása sikeresen befejeződött.",
                    module_updates={
                        "parser": self._build_processing_module(
                            key="parser",
                            status="completed",
                            label="Mondatkinyerés",
                            processed_parts=sentence_count,
                            total_parts=sentence_count,
                            run_id=parser_run.id,
                            message="A parser modul elkészült.",
                        )
                    },
                    document_progress=self._build_document_progress(
                        phase="completed",
                        processed_parts=sentence_count,
                        total_parts=sentence_count,
                        label="A feldolgozás minden lépése elkészült.",
                    ),
                    extra_metadata={
                        "parser_run_id": parser_run.id,
                        "document_id": parsed_document.id if parsed_document is not None else None,
                        "char_count": char_count,
                        "sentence_count": sentence_count,
                    },
                )
                finished_item = self._ingest_item_store.update(
                    replace(
                        finished_item,
                        status="completed",
                        lease_owner=None,
                        lease_expires_at=None,
                        heartbeat_at=_utcnow(),
                        completed_at=_utcnow(),
                        updated_at=_utcnow(),
                    )
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
            safe_error_message = self._truncate_error_message(
                exc,
                max_length=self._PARSER_ERROR_MESSAGE_MAX,
            )
            failed_item = self._ingest_runs().mark_item_failed(
                current_item,
                error_code="processing_failed",
                error_message=safe_error_message,
                progress_message="Ingest feldolgozás közben hiba történt.",
            )
            failed_item = self._update_item_processing_summary(
                failed_item,
                module_updates={
                    "parser": self._build_processing_module(
                        key="parser",
                        status="failed",
                        label="Mondatkinyerés",
                        error_message=safe_error_message,
                    ),
                    "sentence_interpretation": self._build_processing_module(
                        key="sentence_interpretation",
                        status="failed",
                        label="Mondatértelmezés",
                        error_message=safe_error_message,
                    ),
                    "sentence_evaluation": self._build_processing_module(
                        key="sentence_evaluation",
                        status="failed",
                        label="Mondatértékelés",
                        error_message=safe_error_message,
                    ),
                },
            )
            self._record_ingest_event(
                run_id=run_id,
                item_id=current_item.id,
                event_type="item_failed",
                status="failed",
                message=safe_error_message,
                force_reprocess=force_reprocess,
            )
            self._metrics_store.increment("ingest_item_failed_count", 1)
            self._log_step(
                "ingest.item.failed",
                status="error",
                tenant=started_run.tenant,
                ingest_run_id=run_id,
                ingest_item_id=failed_item.id,
            )
            return bool(started_run.continue_on_error)

__all__ = ["IngestItemProcessor"]
