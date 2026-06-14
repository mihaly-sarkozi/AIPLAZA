from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeTopicDto, SpatialMentionDto, TemporalMentionDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_discovery.mapper.discovery_mapper import relationship_dict_to_orm
from apps.kb.kb_discovery.relationships.EntityChunkRelationshipBuilder import (
    EntityChunkRelationshipBuilder,
    EntityCoOccurrenceBuilder,
)
from apps.kb.kb_discovery.relationships.RelationshipScorer import RelationshipScorer
from apps.kb.kb_discovery.relationships.SpatialRelationshipBuilder import SpatialRelationshipBuilder
from apps.kb.kb_discovery.relationships.TemporalRelationshipBuilder import TemporalRelationshipBuilder
from apps.kb.kb_discovery.relationships.TopicRelationshipBuilder import TopicRelationshipBuilder
from apps.kb.kb_discovery.repository.RelationshipRepository import RelationshipRepository


class RelationshipBuildService:
    def __init__(self, relationship_repository: RelationshipRepository) -> None:
        self._relationship_repository = relationship_repository
        self._builders = [
            EntityChunkRelationshipBuilder(),
            EntityCoOccurrenceBuilder(),
            TopicRelationshipBuilder(),
            TemporalRelationshipBuilder(),
            SpatialRelationshipBuilder(),
        ]
        self._scorer = RelationshipScorer()

    def run(
        self,
        ctx: DiscoveryJobContext,
        *,
        entities: list[KnowledgeEntityDto],
        topics: list[KnowledgeTopicDto],
        temporal: list[TemporalMentionDto],
        spatial: list[SpatialMentionDto],
    ) -> int:
        rows = []
        for builder in self._builders:
            builder_name = type(builder).__name__
            for rel in builder.build(
                ctx,
                entities=entities,
                topics=topics,
                temporal=temporal,
                spatial=spatial,
            ):
                rows.append(
                    relationship_dict_to_orm(
                        ctx,
                        rel,
                        builder_name=builder_name,
                        confidence=self._scorer.score(rel),
                    )
                )
        return self._relationship_repository.replace_for_job(ctx.job_id, rows)


__all__ = ["RelationshipBuildService"]
