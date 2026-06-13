from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

from apps.kb.kb_discovery.gazetteers.data_paths import data_file


@dataclass(frozen=True)
class TopicRule:
    topic_key: str
    markers: tuple[str, ...]
    weight: float = 1.0


class TopicTaxonomyProvider:
    TAXONOMY_VERSION = "topics_v1"

    @classmethod
    @lru_cache(maxsize=1)
    def taxonomy(cls) -> dict[str, dict]:
        path = data_file("topics", "topic_taxonomy.json")
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def display_name(cls, topic_key: str, language_code: str) -> str:
        entry = cls.taxonomy().get(topic_key, {})
        names = entry.get("display_name") or {}
        return str(names.get(language_code) or names.get("en") or topic_key)

    @classmethod
    def taxonomy_path(cls, topic_key: str) -> tuple[str, ...]:
        entry = cls.taxonomy().get(topic_key, {})
        path = entry.get("path") or []
        return tuple(str(item) for item in path)


class TopicDictionaryProvider:
    def __init__(self) -> None:
        self._taxonomy = TopicTaxonomyProvider()

    def rules_for(self, language_code: str) -> dict[str, TopicRule]:
        code = (language_code or "en").strip().lower()
        path = data_file("topics", f"topics_{code}.json")
        if not path.is_file():
            path = data_file("topics", "topics_en.json")
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        rules: dict[str, TopicRule] = {}
        for topic_key, entry in payload.items():
            markers = tuple(str(item) for item in entry.get("markers") or ())
            if not markers:
                continue
            rules[topic_key] = TopicRule(
                topic_key=topic_key,
                markers=markers,
                weight=float(entry.get("weight") or 1.0),
            )
        return rules

    def taxonomy_version(self) -> str:
        return self._taxonomy.TAXONOMY_VERSION


__all__ = ["TopicDictionaryProvider", "TopicRule", "TopicTaxonomyProvider"]
