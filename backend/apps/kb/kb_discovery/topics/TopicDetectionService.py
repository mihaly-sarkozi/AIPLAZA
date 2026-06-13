from __future__ import annotations

from apps.kb.kb_discovery.common.TextNormalizer import TextNormalizer
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.enrichment.entity_signals import topic_boosts_from_entities
from apps.kb.kb_discovery.orm.EntityMention import EntityMention
from apps.kb.kb_discovery.topics.TopicDictionaryProvider import TopicDictionaryProvider
from apps.kb.kb_discovery.topics.TopicRuleMatcher import TopicRuleMatcher
from apps.kb.kb_discovery.topics.TopicTaxonomyProvider import TopicTaxonomyProvider


class TopicConfidenceScorer:
    def score(self, *, hits: int, weight: float = 1.0, entity_boost: float = 0.0) -> float:
        return round(min(1.0, (0.45 + 0.12 * hits) * weight + entity_boost), 4)


class TopicDetectionService:
    def __init__(self) -> None:
        self._dictionary = TopicDictionaryProvider()
        self._matcher = TopicRuleMatcher(self._dictionary)
        self._scorer = TopicConfidenceScorer()
        self._taxonomy = TopicTaxonomyProvider()

    def detect_for_chunk(
        self,
        chunk: DiscoveryChunkDto,
        *,
        language_code: str,
        keyword_terms: list[str],
        mentions: list[EntityMention] | None = None,
    ) -> list[KnowledgeTopicDto]:
        from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeTopicDto

        entity_boosts = topic_boosts_from_entities(mentions or [])
        matches = self._matcher.match(chunk.text, language_code=language_code, keyword_terms=keyword_terms)
        for topic_key, boost in entity_boosts.items():
            matches[topic_key] = matches.get(topic_key, 0) + int(boost * 4)

        topics: list[KnowledgeTopicDto] = []
        for topic_key, hits in sorted(matches.items(), key=lambda item: (-item[1], item[0])):
            rule = self._dictionary.rules_for(language_code).get(topic_key)
            weight = rule.weight if rule else 1.0
            confidence = self._scorer.score(
                hits=hits,
                weight=weight,
                entity_boost=entity_boosts.get(topic_key, 0.0),
            )
            topics.append(
                KnowledgeTopicDto(
                    chunk_id=chunk.chunk_id,
                    topic_key=topic_key,
                    display_name=self._taxonomy.display_name(topic_key, language_code),
                    normalized_topic=topic_key,
                    language_code=language_code,
                    confidence=confidence,
                    score=confidence,
                    source="taxonomy_rule" if hits else "entity_signal",
                    taxonomy_version=self._dictionary.taxonomy_version(),
                    metadata={
                        "matched_markers": list(rule.markers[: hits or 0]) if rule else [],
                        "matched_keywords": [term for term in keyword_terms if term],
                        "rule_set": f"topics_{language_code}_v1",
                        "taxonomy_path": list(self._taxonomy.taxonomy_path(topic_key)),
                    },
                )
            )
        return topics


__all__ = ["TopicConfidenceScorer", "TopicDetectionService"]
