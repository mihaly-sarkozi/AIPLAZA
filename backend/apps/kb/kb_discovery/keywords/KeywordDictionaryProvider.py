from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from apps.kb.kb_discovery.gazetteers.data_paths import data_file


@dataclass(frozen=True)
class KeywordDictionaryEntry:
    phrase: str
    aliases: tuple[str, ...]
    category: str
    weight: float


class KeywordDictionaryProvider:
    @classmethod
    @lru_cache(maxsize=8)
    def entries_for(cls, language_code: str) -> dict[str, KeywordDictionaryEntry]:
        code = (language_code or "en").strip().lower()
        path = data_file("keywords", f"keywords_{code}.json")
        if not path.is_file():
            path = data_file("keywords", "keywords_en.json")
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        entries: dict[str, KeywordDictionaryEntry] = {}
        for phrase, raw in payload.items():
            aliases = tuple(str(item) for item in raw.get("aliases") or ())
            entries[phrase.casefold()] = KeywordDictionaryEntry(
                phrase=phrase,
                aliases=aliases,
                category=str(raw.get("category") or ""),
                weight=float(raw.get("weight") or 1.0),
            )
            for alias in aliases:
                entries[alias.casefold()] = KeywordDictionaryEntry(
                    phrase=alias,
                    aliases=(phrase,),
                    category=str(raw.get("category") or ""),
                    weight=float(raw.get("weight") or 1.0),
                )
        return entries


__all__ = ["KeywordDictionaryEntry", "KeywordDictionaryProvider"]
