from __future__ import annotations

from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.topics.TopicDictionaryProvider import TopicDictionaryProvider


class TopicRuleMatcher:
    def __init__(self, dictionary: TopicDictionaryProvider) -> None:
        self._dictionary = dictionary
        self._normalizer = TextNormalizer()

    def match(
        self,
        text: str,
        *,
        language_code: str,
        keyword_terms: list[str] | None = None,
    ) -> dict[str, int]:
        normalized = self._normalizer.normalize(text)
        keyword_set = {term.casefold() for term in keyword_terms or []}
        hits: dict[str, int] = {}
        for topic_key, rule in self._dictionary.rules_for(language_code).items():
            count = sum(1 for marker in rule.markers if marker in normalized)
            count += sum(
                1
                for marker in rule.markers
                if marker.casefold() in keyword_set
            )
            if count:
                hits[topic_key] = count
        return hits


__all__ = ["TopicRuleMatcher"]
