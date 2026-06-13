from __future__ import annotations

from collections import Counter
import re

from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer


class StopwordProvider:
    _WORDS = frozenset(
        {
            "a", "az", "és", "hogy", "van", "egy", "the", "and", "is", "in", "to", "of",
            "használ", "használja", "használják", "tól", "től", "ban", "ben", "ba", "be",
        }
    )

    def is_stopword(self, token: str) -> bool:
        return token in self._WORDS


class TermFrequencyExtractor:
    _TOKEN = re.compile(r"[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]+", re.UNICODE)

    def __init__(self, stopwords: StopwordProvider) -> None:
        self._stopwords = stopwords
        self._normalizer = TextNormalizer()

    def extract(self, text: str) -> list[tuple[str, float]]:
        counter: Counter[str] = Counter()
        for match in self._TOKEN.finditer(text):
            token = self._normalizer.normalize_token(match.group(0))
            if len(token) < 2 or self._stopwords.is_stopword(token):
                continue
            counter[token] += 1
        total = sum(counter.values()) or 1
        return [(term, count / total) for term, count in counter.most_common()]


__all__ = ["StopwordProvider", "TermFrequencyExtractor"]
