from __future__ import annotations

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403


class IngestFacadeMixin:
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
        return self._ingest_listing_service.get_ingest_run(run_id)

    def list_ingest_runs(self, corpus_uuid: str, *, limit: int = 20, offset: int = 0) -> list[IngestRun]:
        return self._ingest_listing_service.list_ingest_runs(corpus_uuid, limit=limit, offset=offset)

    def ingest_run_list_summary(self, corpus_uuid: str) -> dict[str, Any]:
        return self._ingest_listing_service.ingest_run_list_summary(corpus_uuid)

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
        return self._ingest_listing_service.enrich_ingest_items_with_document_metrics(items)

    @staticmethod
    def _ingest_item_char_count(item: IngestItem) -> int:
        return IngestListingService.ingest_item_char_count(item)

    @staticmethod
    def _ingest_item_sentence_count(item: IngestItem) -> int:
        return IngestListingService.ingest_item_sentence_count(item)

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
        self._ingest_item_processor._auto_index_service._ingest_run_store = lambda: self._ingest_run_store
        self._ingest_item_processor.auto_refresh_semantic_block_index_after_ingest(run)


__all__ = ["IngestFacadeMixin"]
