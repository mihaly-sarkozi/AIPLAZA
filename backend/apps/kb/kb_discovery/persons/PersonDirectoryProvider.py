from __future__ import annotations

from typing import Any

from apps.kb.kb_discovery.gazetteers.PersonNicknameGazetteer import PersonNicknameGazetteer


class PersonDirectoryProvider:
    def __init__(
        self,
        entries: list[dict[str, Any]] | None = None,
        nickname_gazetteer: PersonNicknameGazetteer | None = None,
    ) -> None:
        self._entries = list(entries or [])
        self._nickname_gazetteer = nickname_gazetteer or PersonNicknameGazetteer()

    def load(self, *, tenant_slug: str | None, knowledge_base_id: str) -> list[dict[str, Any]]:
        if not self._entries:
            return []
        return self._nickname_gazetteer.expand_directory(self._entries)


__all__ = ["PersonDirectoryProvider"]
