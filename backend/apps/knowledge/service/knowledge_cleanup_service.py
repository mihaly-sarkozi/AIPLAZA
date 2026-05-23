# backend/apps/knowledge/service/knowledge_cleanup_service.py
# Owns corpus cleanup and schema-compatibility fallbacks for missing optional tables.

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import ProgrammingError

from apps.knowledge.errors import KnowledgeBaseNotFound, KnowledgeValidationError

logger = logging.getLogger(__name__)


class KnowledgeCleanupService:
    def __init__(self, facade: Any) -> None:
        self._facade = facade

    def __getattr__(self, name: str) -> Any:
        return getattr(self._facade, name)

    @staticmethod
    def is_missing_table_error(exc: Exception, *table_names: str) -> bool:
        message = str(exc).lower()
        return "does not exist" in message and any(table_name.lower() in message for table_name in table_names)

    @classmethod
    def delete_for_corpus_if_table_exists(cls, store: Any, corpus_uuid: str, *, table_name: str) -> int:
        try:
            return int(store.delete_for_corpus(corpus_uuid))
        except ProgrammingError as exc:
            if cls.is_missing_table_error(exc, table_name):
                logger.warning(
                    "knowledge.clear_contents.skip_missing_table",
                    extra={"corpus_uuid": corpus_uuid, "table_name": table_name},
                )
                return 0
            raise

    @classmethod
    def delete_for_document_if_table_exists(cls, store: Any, document_id: str, *, table_name: str) -> int:
        try:
            return int(store.delete_for_document(document_id))
        except ProgrammingError as exc:
            if cls.is_missing_table_error(exc, table_name):
                logger.warning(
                    "knowledge.reprocess.skip_missing_table",
                    extra={"document_id": document_id, "table_name": table_name},
                )
                return 0
            raise

    def clear_contents(
        self,
        uuid: str,
        *,
        confirm_name: str | None = None,
        current_user_id: int | None = None,
    ) -> dict[str, int]:
        kb = self._corpus_store.get_by_uuid(uuid)
        if not kb:
            raise KnowledgeBaseNotFound()
        kb_name = str(getattr(kb, "name", "") or "")
        if confirm_name and confirm_name != kb_name:
            raise KnowledgeValidationError("Confirmation name does not match")

        file_objects = self._ingest_input_store.list_file_objects_for_corpus(uuid)
        build_collections = {
            str(item.collection_name).strip()
            for item in self._index_build_store.list_for_corpus(uuid)
            if str(item.collection_name).strip()
        }
        base_collection = str(getattr(kb, "qdrant_collection_name", "") or "").strip()
        if base_collection:
            build_collections.add(base_collection)

        deleted_objects = 0
        for bucket_name, object_key in file_objects:
            try:
                self._object_storage.delete_object(key=object_key, bucket=bucket_name)
                deleted_objects += 1
            except Exception:
                logger.warning(
                    "knowledge.clear_contents.object_delete_failed",
                    extra={"bucket": bucket_name, "object_key": object_key, "corpus_uuid": uuid},
                )

        deleted_collections = 0
        vector_index = self._vector_index_factory()
        for collection_name in build_collections:
            try:
                vector_index.delete_collection(collection_name)
                deleted_collections += 1
            except Exception:
                logger.warning(
                    "knowledge.clear_contents.collection_delete_failed",
                    extra={"collection_name": collection_name, "corpus_uuid": uuid},
                )

        deleted_events = self._ingest_event_store.delete_for_corpus(uuid)
        deleted_inputs = self._ingest_input_store.delete_for_corpus(uuid)
        deleted_items = self._ingest_item_store.delete_for_corpus(uuid)
        deleted_runs = self._ingest_run_store.delete_for_corpus(uuid)
        deleted_sentences = self._sentence_store.delete_for_corpus(uuid)
        deleted_paragraphs = self._paragraph_store.delete_for_corpus(uuid)
        deleted_documents = self._document_store.delete_for_corpus(uuid)
        deleted_parser_runs = self._parser_run_store.delete_for_corpus(uuid)
        deleted_claims = (
            self.delete_for_corpus_if_table_exists(self._claim_store, uuid, table_name="knowledge_claims")
            if self._claim_store is not None
            else 0
        )
        deleted_space_time_frames = (
            self.delete_for_corpus_if_table_exists(
                self._space_time_frame_store,
                uuid,
                table_name="knowledge_space_time_frames",
            )
            if self._space_time_frame_store is not None
            else 0
        )
        deleted_mentions = (
            self.delete_for_corpus_if_table_exists(self._mention_store, uuid, table_name="knowledge_mentions")
            if self._mention_store is not None
            else 0
        )
        deleted_sentence_interpretations = (
            self.delete_for_corpus_if_table_exists(
                self._sentence_interpretation_store,
                uuid,
                table_name="knowledge_sentence_interpretations",
            )
            if self._sentence_interpretation_store is not None
            else 0
        )
        deleted_interpretation_runs = (
            self.delete_for_corpus_if_table_exists(
                self._interpretation_run_store,
                uuid,
                table_name="knowledge_interpretation_runs",
            )
            if self._interpretation_run_store is not None
            else 0
        )
        deleted_query_runs = self._query_run_store.delete_for_corpus(uuid)
        deleted_sources = self._source_store.delete_for_corpus(uuid)
        deleted_builds = self._index_build_store.delete_for_corpus(uuid)

        result = {
            "sources": deleted_sources,
            "ingest_runs": deleted_runs,
            "ingest_items": deleted_items,
            "ingest_inputs": deleted_inputs,
            "ingest_events": deleted_events,
            "parser_runs": deleted_parser_runs,
            "documents": deleted_documents,
            "paragraphs": deleted_paragraphs,
            "sentences": deleted_sentences,
            "interpretation_runs": deleted_interpretation_runs,
            "sentence_interpretations": deleted_sentence_interpretations,
            "mentions": deleted_mentions,
            "claims": deleted_claims,
            "space_time_frames": deleted_space_time_frames,
            "index_builds": deleted_builds,
            "query_runs": deleted_query_runs,
            "storage_objects": deleted_objects,
            "vector_collections": deleted_collections,
        }
        self._log_step("corpus.clear_contents", status="ok", corpus_uuid=uuid, **result)
        return result


__all__ = ["KnowledgeCleanupService"]
