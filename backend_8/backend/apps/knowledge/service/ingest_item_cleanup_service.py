from __future__ import annotations

import logging
from typing import Any

from core.kernel.interface.observability import log_structured_event

from apps.knowledge.domain.ingest_item import IngestItem
from apps.knowledge.service.knowledge_cleanup_service import KnowledgeCleanupService

logger = logging.getLogger(__name__)


class IngestItemCleanupService:
    def __init__(
        self,
        *,
        document_store: Any,
        sentence_store: Any,
        paragraph_store: Any,
        parser_run_store: Any,
        source_store: Any,
        space_time_frame_store: Any | None,
        claim_store: Any | None,
        mention_store: Any | None,
        sentence_interpretation_store: Any | None,
        interpretation_run_store: Any | None,
    ) -> None:
        self._document_store = document_store
        self._sentence_store = sentence_store
        self._paragraph_store = paragraph_store
        self._parser_run_store = parser_run_store
        self._source_store = source_store
        self._space_time_frame_store = space_time_frame_store
        self._claim_store = claim_store
        self._mention_store = mention_store
        self._sentence_interpretation_store = sentence_interpretation_store
        self._interpretation_run_store = interpretation_run_store

    def delete_source_parse_outputs(self, source_id: str) -> None:
        self._delete_document_outputs(source_id)
        self._parser_run_store.delete_for_source(source_id)

    def delete_ingest_item_outputs(self, item: IngestItem) -> None:
        source_id = str(item.source_id or item.metadata.get("source_id") or "").strip()
        if not source_id:
            return
        self.delete_source_parse_outputs(source_id)
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

    def _delete_document_outputs(self, source_id: str) -> None:
        document = self._document_store.get_for_source(source_id)
        if document is None:
            return
        for store, table_name in (
            (self._space_time_frame_store, "knowledge_space_time_frames"),
            (self._claim_store, "knowledge_claims"),
            (self._mention_store, "knowledge_mentions"),
            (self._sentence_interpretation_store, "knowledge_sentence_interpretations"),
            (self._interpretation_run_store, "knowledge_interpretation_runs"),
        ):
            if store is not None:
                KnowledgeCleanupService.delete_for_document_if_table_exists(
                    store,
                    document.id,
                    table_name=table_name,
                )
        self._sentence_store.delete_for_document(document.id)
        self._paragraph_store.delete_for_document(document.id)
        self._document_store.delete_for_source(source_id)


__all__ = ["IngestItemCleanupService"]
