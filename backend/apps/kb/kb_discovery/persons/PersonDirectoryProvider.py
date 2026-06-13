from __future__ import annotations

from typing import Any


class PersonDirectoryProvider:
    def __init__(self, entries: list[dict[str, Any]] | None = None) -> None:
        self._entries = list(entries or [])

    def load(self, *, tenant_slug: str | None, knowledge_base_id: str) -> list[dict[str, Any]]:
        return list(self._entries)


__all__ = ["PersonDirectoryProvider"]
