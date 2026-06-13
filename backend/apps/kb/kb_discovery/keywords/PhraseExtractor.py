from __future__ import annotations

import re

from apps.kb.kb_discovery.keywords.StopwordProvider import StopwordProvider


class PhraseExtractor:
    _PHRASE = re.compile(
        r"\b[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]{2,}(?:\s[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]{2,}){0,2}\b",
        re.UNICODE,
    )

    def __init__(self, stopwords: StopwordProvider) -> None:
        self._stopwords = stopwords

    def extract(
        self,
        text: str,
        *,
        language_code: str,
    ) -> list[tuple[str, float, dict[str, object]]]:
        phrases: list[tuple[str, float, dict[str, object]]] = []
        seen: set[str] = set()
        for match in self._PHRASE.finditer(text):
            phrase = match.group(0).strip()
            key = phrase.casefold()
            if key in seen:
                continue
            tokens = key.split()
            if all(self._stopwords.is_stopword(token, language_code=language_code) for token in tokens):
                continue
            if len(tokens) == 1 and self._stopwords.is_stopword(tokens[0], language_code=language_code):
                continue
            seen.add(key)
            phrases.append(
                (
                    phrase,
                    0.5 + 0.1 * len(tokens),
                    {
                        "source": "phrase_extractor",
                        "is_phrase": len(tokens) > 1,
                        "phrase_length": len(tokens),
                        "start_offset": match.start(),
                        "end_offset": match.end(),
                    },
                )
            )
        return phrases


class KeywordRanker:
    def rank(self, items: list[tuple[str, float, dict[str, object]]]) -> list[tuple[str, float, dict[str, object]]]:
        merged: dict[str, tuple[float, dict[str, object]]] = {}
        for term, score, metadata in items:
            key = term.strip()
            if not key:
                continue
            current_score, current_meta = merged.get(key, (0.0, {}))
            merged[key] = (max(current_score, score), {**current_meta, **metadata})
        return sorted(
            [(term, score, metadata) for term, (score, metadata) in merged.items()],
            key=lambda item: (-item[1], item[0].casefold()),
        )


__all__ = ["KeywordRanker", "PhraseExtractor"]
