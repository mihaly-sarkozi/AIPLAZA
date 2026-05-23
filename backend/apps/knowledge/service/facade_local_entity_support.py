from __future__ import annotations

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403


class LocalEntitySupportMixin:
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
        return self._local_entity_cluster_service.resolve_and_persist(
            run=run,
            source=source,
            document=document,
            sentences=sentences,
            mentions=mentions,
            claims=claims,
        )

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

    def _require_corpus(self, corpus_uuid: str) -> Corpus:
        return self._corpus_management_service.require_corpus(corpus_uuid)

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


__all__ = ["LocalEntitySupportMixin"]
