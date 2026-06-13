from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import KnowledgeTopicDto
from apps.kb.kb_discovery.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_discovery.orm.KnowledgeRelationship import KnowledgeRelationship
from apps.kb.kb_discovery.relationships.EntityChunkRelationshipBuilder import (
    EntityChunkRelationshipBuilder,
    EntityCoOccurrenceBuilder,
)
from apps.kb.kb_discovery.relationships.RelationshipScorer import RelationshipScorer
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
        ]
        self._scorer = RelationshipScorer()

    def run(
        self,
        ctx: DiscoveryJobContext,
        *,
        entities: list[KnowledgeEntityDto],
        enrichments: list[KnowledgeEnrichmentDto],
    ) -> int:
        topics = [
            KnowledgeTopicDto(chunk_id=enrichment.chunk_id, topic_key=topic_key, confidence=0.7)
            for enrichment in enrichments
            for topic_key in enrichment.topics
        ]
        rows: list[KnowledgeRelationship] = []
        for builder in self._builders:
            for rel in builder.build(
                ctx,
                entities=entities,
                topics=topics,
                temporal=[],
                spatial=[],
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
        return self._relationship_repository.replace_for_job(ctx.job_id, rows)


__all__ = ["BuildRelationshipsService"]
