from __future__ import annotations

from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.topics.TopicDictionaryProvider import TopicDictionaryProvider


class TopicRuleMatcher:
    def __init__(self, dictionary: TopicDictionaryProvider) -> None:
        self._dictionary = dictionary
        self._normalizer = TextNormalizer()

    def match(self, text: str) -> dict[str, int]:
        normalized = self._normalizer.normalize(text)
        hits: dict[str, int] = {}
        for topic_key, keywords in self._dictionary.rules().items():
            count = sum(1 for keyword in keywords if keyword in normalized)
            if count:
                hits[topic_key] = count
        return hits


class TopicConfidenceScorer:
    def score(self, *, hits: int) -> float:
        return min(1.0, 0.5 + 0.15 * hits)


__all__ = ["TopicConfidenceScorer", "TopicRuleMatcher"]
