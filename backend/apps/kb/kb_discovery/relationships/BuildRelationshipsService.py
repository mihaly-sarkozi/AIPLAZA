from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import RelationshipBuildInput, RelationshipBuildResult
from apps.kb.kb_discovery.mapper.discovery_mapper import relationship_dict_to_orm
from apps.kb.kb_discovery.relationships.EntityChunkRelationshipBuilder import (
    EntityChunkRelationshipBuilder,
    EntityCoOccurrenceBuilder,
)
from apps.kb.kb_discovery.relationships.KeywordRelationshipBuilder import KeywordRelationshipBuilder
from apps.kb.kb_discovery.relationships.ProcessRelationshipBuilder import (
    EntityTopicRelationshipBuilder,
    ProcessRelationshipBuilder,
)
from apps.kb.kb_discovery.relationships.RelationshipScorer import RelationshipScorer
from apps.kb.kb_discovery.relationships.SpatialRelationshipBuilder import SpatialRelationshipBuilder
from apps.kb.kb_discovery.relationships.TemporalRelationshipBuilder import TemporalRelationshipBuilder
from apps.kb.kb_discovery.relationships.TopicRelationshipBuilder import TopicRelationshipBuilder
from apps.kb.kb_discovery.repository.RelationshipRepository import RelationshipRepository


class BuildRelationshipsService:
    def __init__(self, relationship_repository: RelationshipRepository) -> None:
        self._relationship_repository = relationship_repository
        self._builders = [
            EntityChunkRelationshipBuilder(),
            EntityCoOccurrenceBuilder(),
            TopicRelationshipBuilder(),
            KeywordRelationshipBuilder(),
            TemporalRelationshipBuilder(),
            SpatialRelationshipBuilder(),
            ProcessRelationshipBuilder(),
            EntityTopicRelationshipBuilder(),
        ]
        self._scorer = RelationshipScorer()

    def run(self, ctx: DiscoveryJobContext, *, build_input: RelationshipBuildInput) -> RelationshipBuildResult:
        rows = []
        for builder in self._builders:
            builder_name = type(builder).__name__
            for rel in builder.build(
                ctx,
                entities=list(build_input.entities),
                topics=list(build_input.topics),
                keywords=list(build_input.keywords),
                temporal=list(build_input.temporal_mentions),
                spatial=list(build_input.spatial_mentions),
                process_mentions=list(build_input.process_mentions),
            ):
                confidence = self._scorer.score(rel)
                rows.append(
                    relationship_dict_to_orm(
                        ctx,
                        rel,
                        builder_name=builder_name,
                        confidence=confidence,
                    )
                )
        count = self._relationship_repository.replace_for_job(ctx.job_id, rows)
        trace = {
            "relationships_created": count,
            "entity_count": len(build_input.entities),
            "topic_count": len(build_input.topics),
            "keyword_count": len(build_input.keywords),
            "temporal_count": len(build_input.temporal_mentions),
            "spatial_count": len(build_input.spatial_mentions),
            "process_count": len(build_input.process_mentions),
        }
        return RelationshipBuildResult(relationship_count=count, trace=trace)


__all__ = ["BuildRelationshipsService"]
