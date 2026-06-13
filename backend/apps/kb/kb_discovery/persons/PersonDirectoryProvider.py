from __future__ import annotations

from typing import Any

from apps.kb.kb_discovery.gazetteers.PersonNicknameGazetteer import PersonNicknameGazetteer
from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_json


class PersonDirectoryProvider:
    def __init__(
        self,
        entries: list[dict[str, Any]] | None = None,
        nickname_gazetteer: PersonNicknameGazetteer | None = None,
    ) -> None:
        self._extra_entries = list(entries or [])
        self._nickname_gazetteer = nickname_gazetteer or PersonNicknameGazetteer()

    def load(self, *, tenant_slug: str | None, knowledge_base_id: str) -> list[dict[str, Any]]:
        entries = list(self._extra_entries)
        if tenant_slug:
            entries.extend(self._entries_from_payload(
                load_json(data_file("persons", "tenants", f"{tenant_slug}.json"), [])
            ))
        entries.extend(self._entries_from_payload(
            load_json(data_file("persons", "knowledge_bases", f"{knowledge_base_id}.json"), [])
        ))
        if not entries:
            return []
        return self._nickname_gazetteer.expand_directory(self._dedupe_entries(entries))

    @staticmethod
    def _entries_from_payload(payload: object) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            persons = payload.get("persons") or payload.get("entries") or []
            if isinstance(persons, list):
                return [item for item in persons if isinstance(item, dict)]
        return []

    @staticmethod
    def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for entry in entries:
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            key = name.casefold()
            aliases = [
                str(alias).strip()
                for alias in (entry.get("aliases") or [])
                if str(alias).strip()
            ]
            if key in merged:
                existing_aliases = merged[key].setdefault("aliases", [])
                if isinstance(existing_aliases, list):
                    existing_aliases.extend(alias for alias in aliases if alias not in existing_aliases)
            else:
                merged[key] = {"name": name, "aliases": aliases}
        return list(merged.values())


__all__ = ["PersonDirectoryProvider"]
