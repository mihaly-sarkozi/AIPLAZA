from __future__ import annotations

from apps.knowledge.service.facade_mixin_imports import *  # noqa: F401,F403


class SourceFacadeMixin:
    def create_source(
        self,
        *,
        tenant: str,
        corpus_uuid: str,
        title: str,
        source_type: str,
        raw_content: str | None,
        file_ref: str | None,
        created_by: int | None,
    ) -> Source:
        source = Source(
            tenant=tenant,
            corpus_uuid=corpus_uuid,
            title=title,
            source_type=source_type,  # type: ignore[arg-type]
            raw_content=raw_content,
            file_ref=file_ref,
            status="attached",
            created_by=created_by,
            metadata={"content_length": len(raw_content or "")},
        )
        self._metrics_store.increment("source_count", 1)
        self._log_step("source.create", status="ok", tenant=tenant, corpus_uuid=corpus_uuid, source_id=source.id)
        return self._source_store.create(source)

    def list_sources(self, corpus_uuid: str) -> list[Source]:
        return self._source_store.list_for_corpus(corpus_uuid)

    def get_source(self, source_id: str) -> Source | None:
        return self._source_store.get(source_id)

    def get_source_content(self, source_id: str) -> dict[str, Any] | None:
        return self._source_access_service.get_source_content(source_id)

    def user_label(self, user_id: int | None) -> str:
        return self._source_access_service.user_label(user_id)

    def get_source_download(self, source_id: str) -> dict[str, Any] | None:
        return self._source_access_service.get_source_download(source_id)

    def get_query_source_download(self, query_run_id: str, source_id: str) -> dict[str, Any] | None:
        return self._source_access_service.get_query_source_download(query_run_id, source_id)

    def get_query_context_download(self, query_run_id: str) -> dict[str, Any] | None:
        return self._source_access_service.get_query_context_download(query_run_id)

    def parse_source(
        self,
        source_id: str,
        *,
        created_by: int | None = None,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> ParserRun:
        return self._parser_orchestrator.parse_source(
            source_id,
            created_by=created_by,
            progress_callback=progress_callback,
        )


__all__ = ["SourceFacadeMixin"]
