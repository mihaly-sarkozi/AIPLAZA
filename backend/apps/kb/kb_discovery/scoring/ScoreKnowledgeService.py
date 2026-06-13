from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeScoringInput, KnowledgeScoreDto
from apps.kb.kb_discovery.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import EntityMentionDto, KnowledgeEntityDto
from apps.kb.kb_discovery.scoring.KnowledgeScoringService import KnowledgeScoringService


class ScoreKnowledgeService:
    def __init__(self, scoring_service: KnowledgeScoringService) -> None:
        self._scoring = scoring_service

    def run(
        self,
        ctx: DiscoveryJobContext,
        chunks: list[DiscoveryChunkDto],
        *,
        entities: list[KnowledgeEntityDto],
        enrichments: list[KnowledgeEnrichmentDto],
        keywords=None,
        topics=None,
        entity_mentions: list[EntityMentionDto] | None = None,
        temporal_mentions=None,
        spatial_mentions=None,
        process_mentions=None,
        relationship_count: int = 0,
    ) -> list[KnowledgeScoreDto]:
        scoring_input = KnowledgeScoringInput(
            chunks=tuple(chunks),
            enrichments=tuple(enrichments),
            keywords=tuple(keywords or ()),
            topics=tuple(topics or ()),
            entities=tuple(entities),
            entity_mentions=tuple(entity_mentions or ()),
            temporal_mentions=tuple(temporal_mentions or ()),
            spatial_mentions=tuple(spatial_mentions or ()),
            process_mentions=tuple(process_mentions or ()),
            relationship_count=relationship_count,
        )
        return self._scoring.run(ctx, scoring_input)


__all__ = ["ScoreKnowledgeService"]
