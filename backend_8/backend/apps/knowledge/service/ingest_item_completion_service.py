from __future__ import annotations

from dataclasses import replace
from typing import Any

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.service.facade_helpers import utcnow as utcnow


class IngestItemCompletionService:
    def __init__(
        self,
        *,
        ingest_item_store: Any,
        document_store: Any,
        sentence_store: Any,
        progress_service: Any,
        ingest_idempotency_key: Any,
        record_ingest_event: Any,
    ) -> None:
        self._ingest_item_store = ingest_item_store
        self._document_store = document_store
        self._sentence_store = sentence_store
        self._progress_service = progress_service
        self._ingest_idempotency_key = ingest_idempotency_key
        self._record_ingest_event = record_ingest_event

    def mark_parser_handoff(
        self,
        *,
        run_id: str,
        item: IngestItem,
        source: Any,
        content_hash: str,
    ) -> IngestItem:
        finished_item = self._ingest_item_store.update(
            replace(
                item,
                status="processing",
                content_hash=content_hash,
                idempotency_key=self._ingest_idempotency_key(
                    corpus_uuid=item.corpus_uuid,
                    content_hash=content_hash,
                    pipeline_version=item.pipeline_version,
                ),
                progress_message="Ingest lezárva, parserre vár.",
                result_message="Sikeresen előkészítve a parser modulhoz.",
                source_id=source.id,
                completed_at=None,
                updated_at=utcnow(),
                metadata={**item.metadata, "handoff_target": "source_parser", "source_id": source.id},
            )
        )
        self._record_ingest_event(
            run_id=run_id,
            item_id=item.id,
            event_type="source_created",
            status="ok",
            message="Source rekord létrehozva az ingest inputhoz.",
            source_id=source.id,
            source_type=source.source_type,
        )
        self._record_ingest_event(
            run_id=run_id,
            item_id=item.id,
            event_type="parser_handover_ready",
            status="ok",
            message="Az input készen áll a parser modul számára.",
            content_hash=content_hash,
        )
        return self._progress_service.update_item_processing_summary(
            finished_item,
            progress_message="A parser modul megkezdte a dokumentum előkészítését.",
            module_updates={
                "parser": self._progress_service.build_processing_module(
                    key="parser",
                    status="processing",
                    label="Mondatkinyerés",
                    message="A parser modul feldolgozza a dokumentumot.",
                ),
            },
            extra_metadata={"source_id": source.id},
        )

    def mark_completed(self, *, item: IngestItem, source_id: str, parser_run: Any) -> IngestItem:
        parsed_document = self._document_store.get_for_source(source_id)
        sentence_count = 0
        char_count = 0
        if parsed_document is not None:
            char_count = int(parsed_document.char_count or len(parsed_document.text_content or ""))
            sentence_count = len(self._sentence_store.list_for_document(parsed_document.id))
        finished_item = self._progress_service.update_item_processing_summary(
            item,
            progress_message="A dokumentum feldolgozása sikeresen befejeződött.",
            module_updates={
                "parser": self._progress_service.build_processing_module(
                    key="parser",
                    status="completed",
                    label="Mondatkinyerés",
                    processed_parts=sentence_count,
                    total_parts=sentence_count,
                    run_id=parser_run.id,
                    message="A parser modul elkészült.",
                )
            },
            document_progress=self._progress_service.build_document_progress(
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
        return self._ingest_item_store.update(
            replace(
                finished_item,
                status="completed",
                lease_owner=None,
                lease_expires_at=None,
                heartbeat_at=utcnow(),
                completed_at=utcnow(),
                updated_at=utcnow(),
            )
        )


__all__ = ["IngestItemCompletionService"]
