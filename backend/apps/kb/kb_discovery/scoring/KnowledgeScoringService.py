from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import (
    KnowledgeKeywordDto,
    KnowledgeScoreDto,
    KnowledgeTopicDto,
    SpatialMentionDto,
    TemporalMentionDto,
)
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_discovery.mapper.discovery_mapper import score_dto_to_orm
from apps.kb.kb_discovery.repository.ScoreRepository import ScoreRepository
from apps.kb.kb_discovery.scoring.EntityDensityScore import EntityDensityScore
from apps.kb.kb_discovery.scoring.FinalKnowledgeScore import FinalKnowledgeScore
from apps.kb.kb_discovery.scoring.FreshnessScore import FreshnessScore
from apps.kb.kb_discovery.scoring.KeywordQualityScore import KeywordQualityScore
from apps.kb.kb_discovery.scoring.SpatialScore import SpatialScore
from apps.kb.kb_discovery.scoring.StructureScore import StructureScore
from apps.kb.kb_discovery.scoring.TemporalScore import TemporalScore


class KnowledgeScoringService:
    def __init__(self, score_repository: ScoreRepository) -> None:
        self._score_repository = score_repository
        self._freshness = FreshnessScore()
        self._structure = StructureScore()
        self._entity_density = EntityDensityScore()
        self._keyword_quality = KeywordQualityScore()
        self._temporal = TemporalScore()
        self._spatial = SpatialScore()
        self._final = FinalKnowledgeScore()

    def run(
        self,
        ctx: DiscoveryJobContext,
        chunks: list[DiscoveryChunkDto],
        *,
        entities: list[KnowledgeEntityDto],
        keywords: list[KnowledgeKeywordDto],
        topics: list[KnowledgeTopicDto],
        temporal: list[TemporalMentionDto],
        spatial: list[SpatialMentionDto],
        content_types: dict[str, str],
    ) -> list[KnowledgeScoreDto]:
        entity_counts = self._entity_density.counts(entities)
        keyword_counts = self._keyword_quality.counts(keywords)
        temporal_counts = self._temporal.counts(temporal)
        spatial_counts = self._spatial.counts(spatial)
        topic_counts: dict[str, int] = {}
        for topic in topics:
            topic_counts[topic.chunk_id] = topic_counts.get(topic.chunk_id, 0) + 1

        scores: list[KnowledgeScoreDto] = []
        for chunk in chunks:
            components = {
                "freshness": self._freshness.score(),
                "structure": self._structure.score(chunk),
                "entity_density": self._entity_density.score(entity_counts.get(chunk.chunk_id, 0)),
                "keyword_quality": self._keyword_quality.score(keyword_counts.get(chunk.chunk_id, 0)),
                "temporal_score": self._temporal.score(temporal_counts.get(chunk.chunk_id, 0)),
                "spatial_score": self._spatial.score(spatial_counts.get(chunk.chunk_id, 0)),
                "content_type": 0.8 if content_types.get(chunk.chunk_id, "note") != "note" else 0.4,
                "topic_presence": min(1.0, 0.3 * topic_counts.get(chunk.chunk_id, 0)),
            }
            total = self._final.score(components)
            scores.append(
                KnowledgeScoreDto(
                    chunk_id=chunk.chunk_id,
                    knowledge_score=total,
                    components={key: round(value, 4) for key, value in components.items()},
                )
            )
        self._score_repository.replace_for_chunks(
            [chunk.chunk_id for chunk in chunks],
            [score_dto_to_orm(ctx, score) for score in scores],
        )
        return scores


__all__ = ["KnowledgeScoringService"]
