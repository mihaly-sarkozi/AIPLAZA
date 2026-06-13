from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeTopicDto
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.mapper.discovery_mapper import topic_dto_to_orm
from apps.kb.kb_discovery.repository.TopicRepository import TopicRepository
from apps.kb.kb_discovery.topics.TopicDictionaryProvider import TopicDictionaryProvider
from apps.kb.kb_discovery.topics.TopicRuleMatcher import TopicRuleMatcher
from apps.kb.kb_discovery.topics.TopicConfidenceScorer import TopicConfidenceScorer


class TopicDetectionService:
    def __init__(self, topic_repository: TopicRepository) -> None:
        self._topic_repository = topic_repository
        self._dictionary = TopicDictionaryProvider()
        self._matcher = TopicRuleMatcher(self._dictionary)
        self._scorer = TopicConfidenceScorer()

    def run(self, ctx: DiscoveryJobContext, chunks: list[DiscoveryChunkDto]) -> list[KnowledgeTopicDto]:
        topics: list[KnowledgeTopicDto] = []
        for chunk in chunks:
            for topic_key, hits in self._matcher.match(chunk.text).items():
                topics.append(
                    KnowledgeTopicDto(
                        chunk_id=chunk.chunk_id,
                        topic_key=topic_key,
                        confidence=self._scorer.score(hits=hits),
                    )
                )
        self._topic_repository.replace_for_job(
            ctx.job_id, [topic_dto_to_orm(ctx, topic) for topic in topics]
        )
        return topics


__all__ = ["TopicDetectionService"]
