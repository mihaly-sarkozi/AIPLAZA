from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.exc import ProgrammingError

from apps.knowledge.domain.search_profile import SearchProfile
from apps.knowledge.service.facade_helpers import search_profile_from_trace_payload


class ProfileHistoryService:
    def __init__(
        self,
        *,
        interpretation_run_store: Any | None,
        is_missing_table_error: Callable[..., bool],
    ) -> None:
        self._interpretation_run_store = interpretation_run_store
        self._is_missing_table_error = is_missing_table_error

    @staticmethod
    def _store(value: Any | None) -> Any | None:
        return value() if callable(value) else value

    def _completed_runs(self, *, corpus_uuid: str, exclude_interpretation_run_id: str | None, limit: int) -> list[Any]:
        interpretation_run_store = self._store(self._interpretation_run_store)
        if interpretation_run_store is None:
            return []
        list_for_corpus = getattr(interpretation_run_store, "list_for_corpus", None)
        if not callable(list_for_corpus):
            return []
        try:
            runs = list_for_corpus(corpus_uuid, limit=limit)
        except ProgrammingError as exc:
            if self._is_missing_table_error(exc, "knowledge_interpretation_runs"):
                return []
            raise
        return [
            run
            for run in runs
            if str(run.id) != str(exclude_interpretation_run_id or "") and run.status == "completed"
        ]

    def load_search_profiles(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[SearchProfile]:
        profiles: list[SearchProfile] = []
        for run in self._completed_runs(
            corpus_uuid=corpus_uuid,
            exclude_interpretation_run_id=exclude_interpretation_run_id,
            limit=limit,
        ):
            for item in dict(run.metadata or {}).get("search_profiles") or []:
                profile = search_profile_from_trace_payload(item) if isinstance(item, dict) else None
                if profile is not None:
                    profiles.append(profile)
        return profiles

    def load_global_profiles(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        profiles_by_id: dict[str, dict[str, Any]] = {}
        for run in reversed(
            self._completed_runs(
                corpus_uuid=corpus_uuid,
                exclude_interpretation_run_id=exclude_interpretation_run_id,
                limit=limit,
            )
        ):
            for item in dict(run.metadata or {}).get("global_profiles") or []:
                if isinstance(item, dict) and str(item.get("profile_id") or ""):
                    profiles_by_id[str(item.get("profile_id"))] = dict(item)
        return list(profiles_by_id.values())

    def load_retrieval_chunks(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        chunks_by_profile_id: dict[str, dict[str, Any]] = {}
        for run in reversed(
            self._completed_runs(
                corpus_uuid=corpus_uuid,
                exclude_interpretation_run_id=exclude_interpretation_run_id,
                limit=limit,
            )
        ):
            for item in dict(run.metadata or {}).get("retrieval_chunks") or []:
                if isinstance(item, dict) and str(item.get("profile_id") or ""):
                    chunks_by_profile_id[str(item.get("profile_id"))] = dict(item)
        return list(chunks_by_profile_id.values())

    def load_semantic_blocks(
        self,
        *,
        corpus_uuid: str,
        exclude_interpretation_run_id: str | None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        blocks_by_id: dict[str, dict[str, Any]] = {}
        for run in reversed(
            self._completed_runs(
                corpus_uuid=corpus_uuid,
                exclude_interpretation_run_id=exclude_interpretation_run_id,
                limit=limit,
            )
        ):
            for item in dict(run.metadata or {}).get("semantic_blocks") or []:
                if isinstance(item, dict) and str(item.get("id") or ""):
                    blocks_by_id[str(item.get("id"))] = dict(item)
        return list(blocks_by_id.values())


__all__ = ["ProfileHistoryService"]
