from __future__ import annotations

# backend/apps/kb/kb_understanding/service/BuildRelationshipsService.py
# Feladat: Kapcsolatok építése entitások, chunkok, dokumentum és témák között.
# Sárközi Mihály - 2026.06.11

from collections import defaultdict

from apps.kb.kb_understanding.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_understanding.dto.KnowledgeEntityDto import KnowledgeEntityDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.orm.KnowledgeRelationship import KnowledgeRelationship
from apps.kb.kb_understanding.repository.RelationshipRepository import RelationshipRepository
from apps.kb.shared.ids import new_id


class BuildRelationshipsService:
    def __init__(self, relationship_repository: RelationshipRepository) -> None:
        self._relationship_repository = relationship_repository

    def run(
        self,
        ctx: UnderstandingJobContext,
        entities: list[KnowledgeEntityDto],
        enrichments: list[KnowledgeEnrichmentDto] | None = None,
    ) -> int:
        """Visszaadja a mentett kapcsolatok számát."""
        rows: list[KnowledgeRelationship] = []

        def add(from_type: str, from_id: str, to_type: str, to_id: str, relation: str, confidence: float) -> None:
            rows.append(
                KnowledgeRelationship(
                    id=new_id("rel"),
                    job_id=ctx.job_id,
                    knowledge_base_id=ctx.knowledge_base_id,
                    from_type=from_type,
                    from_id=from_id,
                    to_type=to_type,
                    to_id=to_id,
                    relation=relation,
                    confidence=confidence,
                )
            )

        # entity ↔ chunk és entity ↔ document.
        for entity in entities:
            entity_key = f"{entity.entity_type.value}:{entity.normalized_name}"
            for chunk_id in entity.chunk_ids:
                add("entity", entity_key, "chunk", chunk_id, "mentioned_in", entity.confidence)
            add("entity", entity_key, "document", ctx.training_item_id, "appears_in", entity.confidence)

        # entity ↔ entity: közös chunk-előfordulás.
        chunk_entities: dict[str, list[KnowledgeEntityDto]] = defaultdict(list)
        for entity in entities:
            for chunk_id in entity.chunk_ids:
                chunk_entities[chunk_id].append(entity)
        seen_pairs: set[tuple[str, str]] = set()
        for co_occurring in chunk_entities.values():
            for index, first in enumerate(co_occurring):
                for second in co_occurring[index + 1 :]:
                    first_key = f"{first.entity_type.value}:{first.normalized_name}"
                    second_key = f"{second.entity_type.value}:{second.normalized_name}"
                    pair = tuple(sorted((first_key, second_key)))
                    if first_key == second_key or pair in seen_pairs:
                        continue
                    seen_pairs.add(pair)
                    add(
                        "entity",
                        pair[0],
                        "entity",
                        pair[1],
                        "related_to",
                        min(first.confidence, second.confidence),
                    )

        # topic ↔ document és topic ↔ chunk.
        seen_topics: set[str] = set()
        for enrichment in enrichments or []:
            for topic in enrichment.topics:
                topic_key = topic.strip().lower()
                if not topic_key:
                    continue
                add("topic", topic_key, "chunk", enrichment.chunk_id, "has_topic", enrichment.confidence)
                if topic_key not in seen_topics:
                    seen_topics.add(topic_key)
                    add(
                        "topic",
                        topic_key,
                        "document",
                        ctx.training_item_id,
                        "has_topic",
                        enrichment.confidence,
                    )

        return self._relationship_repository.replace_for_job(ctx.job_id, rows)


__all__ = ["BuildRelationshipsService"]
