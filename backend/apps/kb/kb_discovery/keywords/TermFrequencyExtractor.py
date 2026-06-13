from __future__ import annotations

from collections import Counter
import re

from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.enums.SupportedLanguage import SupportedLanguage
from apps.kb.kb_discovery.languages.language_profiles import stopwords_for


class StopwordProvider:
    def for_language(self, language_code: str) -> frozenset[str]:
        code = (language_code or SupportedLanguage.UNKNOWN.value).strip().lower()
        if code in SupportedLanguage._value2member_map_:
            return stopwords_for(SupportedLanguage(code))
        return stopwords_for(SupportedLanguage.UNKNOWN)

    def is_stopword(self, token: str, *, language_code: str) -> bool:
        return token.casefold() in {word.casefold() for word in self.for_language(language_code)}


class TermFrequencyExtractor:
    _TOKEN = re.compile(r"[\wÁÉÍÓÖŐÚÜŰáéíóöőúüű-]+", re.UNICODE)

    def __init__(self, stopwords: StopwordProvider) -> None:
        self._stopwords = stopwords
        self._normalizer = TextNormalizer()

    def extract(
        self,
        text: str,
        *,
        language_code: str,
    ) -> list[tuple[str, float, dict[str, object]]]:
        counter: Counter[str] = Counter()
        offsets: dict[str, tuple[int, int]] = {}
        for match in self._TOKEN.finditer(text):
            token = self._normalizer.normalize_token(match.group(0))
            if len(token) < 2 or self._stopwords.is_stopword(token, language_code=language_code):
                continue
            counter[token] += 1
            offsets.setdefault(token, (match.start(), match.end()))
        total = sum(counter.values()) or 1
        return [
            (
                term,
                count / total,
                {
                    "source": "term_frequency",
                    "frequency": count,
                    "start_offset": offsets[term][0],
                    "end_offset": offsets[term][1],
                },
            )
            for term, count in counter.most_common()
        ]


__all__ = ["StopwordProvider", "TermFrequencyExtractor"]
