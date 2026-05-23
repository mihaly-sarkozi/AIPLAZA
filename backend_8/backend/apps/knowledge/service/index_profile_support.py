from __future__ import annotations

import threading
from typing import Any

from apps.knowledge.domain.index_profile import DEFAULT_INDEX_PROFILE, IndexProfile


class IndexProfileSupport:
    def __init__(self, *, index_profile_store: Any) -> None:
        self._index_profile_store = index_profile_store
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def default_index_profile(self, key: str | None = None) -> IndexProfile:
        if key:
            profile = self._index_profile_store.get(key)
            if profile is not None:
                return profile
        return DEFAULT_INDEX_PROFILE

    @staticmethod
    def vector_size_for_profile(profile: IndexProfile, vector_index: Any) -> int | None:
        configured = dict(profile.config or {}).get("vector_size")
        if configured is not None:
            try:
                value = int(configured)
                if value > 0:
                    return value
            except (TypeError, ValueError):
                pass
        try:
            value = int(getattr(vector_index, "vector_size", None))
            return value if value > 0 else None
        except (TypeError, ValueError):
            return None

    def index_build_lock(self, build_id: str) -> threading.Lock:
        with self._locks_guard:
            lock = self._locks.get(build_id)
            if lock is None:
                lock = threading.Lock()
                self._locks[build_id] = lock
            return lock


__all__ = ["IndexProfileSupport"]
