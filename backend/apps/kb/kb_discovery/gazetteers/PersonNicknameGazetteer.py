from __future__ import annotations

import re

from apps.kb.kb_discovery.gazetteers.data_paths import data_file
from apps.kb.kb_discovery.gazetteers.loaders import load_alias_rows


class PersonNicknameGazetteer:
    def __init__(self) -> None:
        self._rows = (
            load_alias_rows(data_file("person_aliases", "person_aliases_hu.csv"))
            + load_alias_rows(data_file("person_aliases", "person_aliases_en.csv"))
            + load_alias_rows(data_file("person_aliases", "person_aliases_es.csv"))
        )
        self._aliases_by_canonical: dict[str, list[str]] = {}
        for row in self._rows:
            canonical = row["canonical_name"]
            alias = row["alias"]
            self._aliases_by_canonical.setdefault(canonical.casefold(), []).append(alias)

    def expand_directory(self, directory: list[dict]) -> list[dict]:
        expanded: list[dict] = []
        for entry in directory:
            canonical = str(entry.get("name") or "").strip()
            if not canonical:
                continue
            aliases = [str(item).strip() for item in (entry.get("aliases") or []) if str(item).strip()]
            for alias in self._aliases_by_canonical.get(canonical.casefold(), []):
                if alias not in aliases:
                    aliases.append(alias)
            expanded.append({"name": canonical, "aliases": aliases})
        return expanded


__all__ = ["PersonNicknameGazetteer"]
