from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import RelationshipBuildInput, RelationshipBuildResult
from apps.kb.kb_discovery.orm.KnowledgeRelationship import KnowledgeRelationship
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
from apps.kb.shared.ids import new_id


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
        rows: list[KnowledgeRelationship] = []
        for builder in self._builders:
            for rel in builder.build(
                ctx,
                entities=list(build_input.entities),
                topics=list(build_input.topics),
                keywords=list(build_input.keywords),
                temporal=list(build_input.temporal_mentions),
                spatial=list(build_input.spatial_mentions),
                process_mentions=list(build_input.process_mentions),
            ):
                rows.append(
                    KnowledgeRelationship(
                        id=new_id("rel"),
                        job_id=ctx.job_id,
                        knowledge_base_id=ctx.knowledge_base_id,
                        from_type=rel["from_type"],
                        from_id=rel["from_id"],
                        to_type=rel["to_type"],
                        to_id=rel["to_id"],
                        relation=rel["relation"],
                        confidence=self._scorer.score(rel),
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
