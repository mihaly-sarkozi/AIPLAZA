from __future__ import annotations

from dataclasses import replace
from typing import Any

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.service.facade_helpers import utcnow as utcnow


class IngestDuplicateService:
    def __init__(
        self,
        *,
        ingest_item_store: Any,
        progress_service: Any,
        ingest_idempotency_key: Any,
        record_ingest_event: Any,
    ) -> None:
        self._ingest_item_store = ingest_item_store
        self._progress_service = progress_service
        self._ingest_idempotency_key = ingest_idempotency_key
        self._record_ingest_event = record_ingest_event

    def find_duplicate(self, item: IngestItem, *, content_hash: str, force_reprocess: bool) -> IngestItem | None:
        if force_reprocess:
            return None
        return self._ingest_item_store.find_by_hash(
            corpus_uuid=item.corpus_uuid,
            content_hash=content_hash,
            exclude_item_id=item.id,
            pipeline_version=item.pipeline_version,
        )

    def mark_duplicate(
        self,
        *,
        run_id: str,
        item: IngestItem,
        duplicate: IngestItem,
        content_hash: str,
    ) -> IngestItem:
        finished_item = self._ingest_item_store.update(
            replace(
                item,
                status="duplicate",
                content_hash=content_hash,
                duplicate_of_item_id=duplicate.id,
                duplicate_of_source_id=duplicate.source_id,
                idempotency_key=self._ingest_idempotency_key(
                    corpus_uuid=item.corpus_uuid,
                    content_hash=content_hash,
                    pipeline_version=item.pipeline_version,
                ),
                result_message="Duplikátumként jelölve.",
                progress_message="Duplikált input, parser nem indul.",
                lease_owner=None,
                lease_expires_at=None,
                heartbeat_at=utcnow(),
                completed_at=utcnow(),
                updated_at=utcnow(),
            )
        )
        finished_item = self._progress_service.update_item_processing_summary(
            finished_item,
            module_updates={
                "parser": self._progress_service.build_processing_module(
                    key="parser",
                    status="skipped",
                    label="Mondatkinyerés",
                    message="Duplikátum miatt nem indult parser.",
                ),
                "sentence_interpretation": self._progress_service.build_processing_module(
                    key="sentence_interpretation",
                    status="skipped",
                    label="Mondatértelmezés",
                    message="Duplikátum miatt nem indult értelmezés.",
                ),
                "sentence_evaluation": self._progress_service.build_processing_module(
                    key="sentence_evaluation",
                    status="skipped",
                    label="Mondatértékelés",
                    message="Duplikátum miatt nem indult értékelés.",
                ),
            },
            document_progress=self._progress_service.build_document_progress(
                phase="duplicate",
                processed_parts=0,
                total_parts=0,
                label="Duplikátumként jelölve, nincs további feldolgozás.",
            ),
        )
        self._record_ingest_event(
            run_id=run_id,
            item_id=item.id,
            event_type="duplicate_detected",
            status="ok",
            message="Duplikált input felismerve.",
            duplicate_of_item_id=duplicate.id,
            content_hash=content_hash,
        )
        return finished_item


__all__ = ["IngestDuplicateService"]
