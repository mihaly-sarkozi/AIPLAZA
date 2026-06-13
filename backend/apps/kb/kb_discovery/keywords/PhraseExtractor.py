from __future__ import annotations

import re

from apps.kb.kb_discovery.keywords.StopwordProvider import StopwordProvider


class PhraseExtractor:
    _PHRASE = re.compile(r"\b[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]{2,}(?:\s[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]{2,}){0,2}\b", re.UNICODE)

    def __init__(self, stopwords: StopwordProvider) -> None:
        self._stopwords = stopwords

    def extract(self, text: str) -> list[tuple[str, float]]:
        phrases: list[tuple[str, float]] = []
        seen: set[str] = set()
        for match in self._PHRASE.finditer(text):
            phrase = match.group(0).strip()
            key = phrase.lower()
            if key in seen:
                continue
            tokens = key.split()
            if all(self._stopwords.is_stopword(token) for token in tokens):
                continue
            if len(tokens) == 1 and self._stopwords.is_stopword(tokens[0]):
                continue
            seen.add(key)
            phrases.append((phrase, 0.5 + 0.1 * len(tokens)))
        return phrases


class KeywordRanker:
    def rank(self, items: list[tuple[str, float]]) -> list[tuple[str, float]]:
        merged: dict[str, float] = {}
        for term, score in items:
            key = term.strip()
            if not key:
                continue
            merged[key] = max(merged.get(key, 0.0), score)
        return sorted(merged.items(), key=lambda item: (-item[1], item[0]))


__all__ = ["KeywordRanker", "PhraseExtractor"]
