from __future__ import annotations

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403


class InternalFacadeMixin:
    def _ingest_runs(self) -> IngestRunService:
        return IngestRunService(
            ingest_run_store=self._ingest_run_store,
            ingest_item_store=self._ingest_item_store,
            progress_summary_builder=self._ingest_progress_service.build_run_summary,
            quality_diagnostics_builder=_aggregate_ingest_item_quality,
        )

    def _log_step(self, step: str, *, status: str, tenant: str | None = None, duration_ms: float | None = None, **counts: object) -> None:
        payload = {
            "step": step,
            "status": status,
            "tenant": tenant,
            "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        }
        payload.update(counts)
        logger.info("knowledge.pipeline", extra={"knowledge": payload})

    @staticmethod
    def _delete_for_corpus_if_table_exists(store: Any, corpus_uuid: str, *, table_name: str) -> int:
        return KnowledgeCleanupService.delete_for_corpus_if_table_exists(store, corpus_uuid, table_name=table_name)

    @staticmethod
    def _delete_for_document_if_table_exists(store: Any, document_id: str, *, table_name: str) -> int:
        return KnowledgeCleanupService.delete_for_document_if_table_exists(store, document_id, table_name=table_name)

    @staticmethod
    def _is_missing_table_error(exc: Exception, *table_names: str) -> bool:
        return KnowledgeCleanupService.is_missing_table_error(exc, *table_names)

    @staticmethod
    def _truncate_error_message(value: Any, *, max_length: int) -> str:
        text = str(value or "").strip()
        if len(text) <= max_length:
            return text
        suffix = "... [truncated]"
        keep = max(0, max_length - len(suffix))
        return f"{text[:keep]}{suffix}"

    def _load_existing_search_profiles(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[SearchProfile]:
        return self._profile_history_service.load_search_profiles(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=exclude_interpretation_run_id,
            limit=limit,
        )

    def _load_existing_global_profiles(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self._profile_history_service.load_global_profiles(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=exclude_interpretation_run_id,
            limit=limit,
        )

    def _load_existing_retrieval_chunks(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self._profile_history_service.load_retrieval_chunks(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=exclude_interpretation_run_id,
            limit=limit,
        )

    def _load_existing_semantic_blocks(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        return self._profile_history_service.load_semantic_blocks(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=exclude_interpretation_run_id,
            limit=limit,
        )

    @staticmethod
    def _semantic_block_search_text(block: dict[str, Any]) -> str:
        return semantic_block_search_text(block)

    @staticmethod
    def _query_terms_for_blocks(query_profile: dict[str, Any] | None, query: str | None) -> set[str]:
        return query_terms_for_blocks(query_profile, query)

    @staticmethod
    def _query_phrase_for_blocks(query: str | None) -> str:
        return query_phrase_for_blocks(query)

    @staticmethod
    def _is_broad_function_query(query: str | None, query_profile: dict[str, Any] | None) -> bool:
        return is_broad_function_query(query, query_profile)

    @staticmethod
    def _select_semantic_blocks_for_query(
        *,
        semantic_blocks: list[dict[str, Any]],
        matched_claims: list[dict[str, Any]],
        matched_chunks: list[dict[str, Any]],
        query_profile: dict[str, Any] | None = None,
        query: str | None = None,
        max_blocks: int = 4,
    ) -> list[dict[str, Any]]:
        return select_semantic_blocks_for_query(
            semantic_blocks=semantic_blocks,
            matched_claims=matched_claims,
            matched_chunks=matched_chunks,
            query_profile=query_profile,
            query=query,
            max_blocks=max_blocks,
        )

    @staticmethod
    def _semantic_blocks_context(blocks: list[dict[str, Any]], *, max_chars: int = 6000) -> str:
        return semantic_blocks_context(blocks, max_chars=max_chars)

    @staticmethod
    def _filter_relevant_semantic_blocks(
        blocks: list[dict[str, Any]],
        *,
        max_blocks: int = 4,
        score_floor: float = 0.25,
        relative_floor_ratio: float = 0.8,
    ) -> list[dict[str, Any]]:
        return filter_relevant_semantic_blocks(
            blocks,
            max_blocks=max_blocks,
            score_floor=score_floor,
            relative_floor_ratio=relative_floor_ratio,
        )

    @staticmethod
    def _retrieval_chunks_from_vector_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return retrieval_chunks_from_vector_hits(hits)

    @staticmethod
    def _semantic_blocks_from_vector_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return semantic_blocks_from_vector_hits(hits)

    @staticmethod
    def _order_chunks_by_vector_hits(retrieval_chunks: list[dict[str, Any]], hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return order_chunks_by_vector_hits(retrieval_chunks, hits)

    @staticmethod
    def _to_corpus(item: Any, *, tenant: str = "") -> Corpus:
        return CorpusManagementService.to_corpus(item, tenant=tenant)

    def _user_repo_list_all(self) -> list[Any]:
        if self._user_repo is None or not hasattr(self._user_repo, "list_all"):
            return []
        return self._user_repo.list_all()

    def _default_index_profile(self, key: str | None = None) -> IndexProfile:
        return self._index_profile_support.default_index_profile(key)

    @staticmethod
    def _vector_size_for_profile(profile: IndexProfile, vector_index: Any) -> int | None:
        return IndexProfileSupport.vector_size_for_profile(profile, vector_index)

    def _index_build_lock(self, build_id: str) -> threading.Lock:
        return self._index_profile_support.index_build_lock(build_id)

    @staticmethod
    def _sha256_bytes(content: bytes) -> str:
        return IngestRunCreationService._sha256_bytes(content)

    @staticmethod
    def _sha256_text(content: str) -> str:
        return IngestRunCreationService._sha256_text(content)

    @staticmethod
    def _ingest_pipeline_version() -> str:
        return IngestRunCreationService.ingest_pipeline_version()

    @classmethod
    def _ingest_idempotency_key(cls, *, corpus_uuid: str, content_hash: str, pipeline_version: str | None = None) -> str:
        return IngestRunCreationService.ingest_idempotency_key(
            corpus_uuid=corpus_uuid,
            content_hash=content_hash,
            pipeline_version=pipeline_version,
        )

    def _record_ingest_event(
        self,
        *,
        run_id: str,
        event_type: str,
        status: str,
        item_id: str | None = None,
        message: str | None = None,
        created_by: int | None = None,
        **details: Any,
    ) -> IngestEvent:
        return self._ingest_run_creation_service.record_ingest_event(
            run_id=run_id,
            event_type=event_type,
            status=status,
            item_id=item_id,
            message=message,
            created_by=created_by,
            **details,
        )


__all__ = ["InternalFacadeMixin"]
