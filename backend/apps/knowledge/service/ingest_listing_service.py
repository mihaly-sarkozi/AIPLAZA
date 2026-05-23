from __future__ import annotations

from dataclasses import replace
from typing import Any

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.domain.ingest_run import IngestRun


class IngestListingService:
    def __init__(
        self,
        *,
        ingest_run_store: Any,
        ingest_item_store: Any,
        document_store: Any,
        refresh_ingest_run: Any,
        list_ingest_items: Any,
    ) -> None:
        self._ingest_run_store = ingest_run_store
        self._ingest_item_store = ingest_item_store
        self._document_store = document_store
        self._refresh_ingest_run = refresh_ingest_run
        self._list_ingest_items = list_ingest_items

    @staticmethod
    def _store(value: Any) -> Any:
        return value() if callable(value) else value

    def get_ingest_run(self, run_id: str) -> IngestRun | None:
        run = self._store(self._ingest_run_store).get(run_id)
        if run is None:
            return None
        if run.status in {"queued", "processing"}:
            return self._refresh_ingest_run(run_id)
        return run

    def list_ingest_runs(self, corpus_uuid: str, *, limit: int = 20, offset: int = 0) -> list[IngestRun]:
        runs = self._store(self._ingest_run_store).list_for_corpus(corpus_uuid, limit=limit, offset=offset)
        return [self._refresh_ingest_run(run.id) if run.status in {"queued", "processing"} else run for run in runs]

    def ingest_run_list_summary(self, corpus_uuid: str) -> dict[str, Any]:
        total_run_count = None
        ingest_run_store = self._store(self._ingest_run_store)
        ingest_item_store = self._store(self._ingest_item_store)
        if hasattr(ingest_run_store, "count_for_corpus"):
            total_run_count = int(ingest_run_store.count_for_corpus(corpus_uuid))
        if hasattr(ingest_item_store, "list_for_corpus"):
            all_items = ingest_item_store.list_for_corpus(corpus_uuid)
        else:
            runs = self.list_ingest_runs(corpus_uuid, limit=1000, offset=0)
            all_items = [item for run in runs for item in self._list_ingest_items(run.id)]
            if total_run_count is None:
                total_run_count = len(runs)
        total_char_count = 0
        total_sentence_count = 0
        for item in all_items:
            item_char_count = self.ingest_item_char_count(item)
            if item_char_count <= 0 and item.source_id:
                document = self._store(self._document_store).get_for_source(item.source_id)
                if document is not None:
                    item_char_count = int(document.char_count or len(document.text_content or ""))
            total_char_count += item_char_count
            total_sentence_count += self.ingest_item_sentence_count(item)
        return {
            "total_run_count": int(total_run_count or 0),
            "total_item_count": len(all_items),
            "total_char_count": total_char_count,
            "total_sentence_count": total_sentence_count,
        }

    def enrich_ingest_items_with_document_metrics(self, items: list[IngestItem]) -> list[IngestItem]:
        enriched: list[IngestItem] = []
        for item in items:
            metadata = dict(item.metadata or {})
            if self.ingest_item_char_count(item) <= 0 and item.source_id:
                document = self._store(self._document_store).get_for_source(item.source_id)
                if document is not None:
                    metadata["char_count"] = int(document.char_count or len(document.text_content or ""))
            enriched.append(replace(item, metadata=metadata) if metadata != (item.metadata or {}) else item)
        return enriched

    @staticmethod
    def ingest_item_char_count(item: IngestItem) -> int:
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
    def ingest_item_sentence_count(item: IngestItem) -> int:
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


__all__ = ["IngestListingService"]
