from __future__ import annotations

from typing import Any

from apps.knowledge.domain.index_build import IndexBuild


class RetrievalBuildResolver:
    def __init__(self, *, index_build_store: Any) -> None:
        self._index_build_store = index_build_store

    def resolve_builds(self, *, corpus_uuid: str, build_ids: list[str] | None = None) -> list[IndexBuild]:
        if build_ids:
            builds = [self._index_build_store.get(build_id) for build_id in build_ids]
        else:
            builds = self._index_build_store.list_for_corpus(corpus_uuid)[:1]
        return [item for item in builds if self.is_ready_build(item)]

    @staticmethod
    def is_ready_build(item: IndexBuild | None) -> bool:
        if item is None:
            return False
        status = str(getattr(item, "status", "") or "").strip().lower()
        if status in {"ready", "completed", "success", "succeeded", "done"}:
            return True
        progress_state = str((getattr(item, "metadata", {}) or {}).get("index_progress_state") or "").strip().lower()
        return progress_state in {"index_ready", "ready", "completed", "done"}


__all__ = ["RetrievalBuildResolver"]
