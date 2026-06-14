from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from apps.kb.kb_discovery.orm.EntityMention import EntityMention
from apps.kb.kb_discovery.orm.KnowledgeEnrichment import KnowledgeEnrichment
from apps.kb.kb_discovery.orm.KnowledgeEntity import KnowledgeEntity
from apps.kb.kb_discovery.orm.KnowledgeKeyword import KnowledgeKeyword
from apps.kb.kb_discovery.orm.KnowledgeRelationship import KnowledgeRelationship
from apps.kb.kb_discovery.orm.KnowledgeScore import KnowledgeScore
from apps.kb.kb_discovery.orm.KnowledgeTopic import KnowledgeTopic
from apps.kb.kb_discovery.orm.ProcessMention import ProcessMention
from apps.kb.kb_discovery.orm.SpatialMention import SpatialMention
from apps.kb.kb_discovery.orm.TemporalMention import TemporalMention
from apps.kb.kb_discovery.repository.EnrichmentRepository import EnrichmentRepository
from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository
from apps.kb.kb_discovery.repository.ProcessRepository import ProcessRepository
from apps.kb.kb_discovery.repository.RelationshipRepository import RelationshipRepository
from apps.kb.kb_discovery.repository.ScoreRepository import ScoreRepository
from apps.kb.kb_discovery.repository.SpatialRepository import SpatialRepository
from apps.kb.kb_discovery.repository.TemporalRepository import TemporalRepository


@dataclass(frozen=True)
class DiscoveryChunkBundle:
    chunk_id: str
    language_code: str | None = None
    enrichment: KnowledgeEnrichment | None = None
    keywords: tuple[KnowledgeKeyword, ...] = ()
    topics: tuple[KnowledgeTopic, ...] = ()
    entities: tuple[KnowledgeEntity, ...] = ()
    entity_mentions: tuple[EntityMention, ...] = ()
    temporal_mentions: tuple[TemporalMention, ...] = ()
    spatial_mentions: tuple[SpatialMention, ...] = ()
    process_mentions: tuple[ProcessMention, ...] = ()
    relationships: tuple[KnowledgeRelationship, ...] = ()
    score: KnowledgeScore | None = None


class DiscoveryBundleRepository:
    def __init__(
        self,
        enrichment_repository: EnrichmentRepository,
        entity_repository: EntityRepository,
        mention_repository: EntityMentionRepository,
        temporal_repository: TemporalRepository,
        spatial_repository: SpatialRepository,
        process_repository: ProcessRepository,
        relationship_repository: RelationshipRepository,
        score_repository: ScoreRepository,
    ) -> None:
        self._enrichment_repository = enrichment_repository
        self._entity_repository = entity_repository
        self._mention_repository = mention_repository
        self._temporal_repository = temporal_repository
        self._spatial_repository = spatial_repository
        self._process_repository = process_repository
        self._relationship_repository = relationship_repository
        self._score_repository = score_repository

    def get_bundle_for_chunks(
        self,
        job_id: str,
        training_item_id: str,
        chunk_ids: list[str],
    ) -> dict[str, DiscoveryChunkBundle]:
        if not chunk_ids:
            return {}

        enrichment_bundles = self._enrichment_repository.get_enrichment_bundle_for_chunks(job_id, chunk_ids)
        entities = self._entity_repository.list_for_chunks(training_item_id, chunk_ids)
        mentions_by_chunk = self._mention_repository.list_by_job_grouped_by_chunk(job_id)
        temporal_mentions = self._temporal_repository.list_for_chunks(job_id, chunk_ids)
        spatial_mentions = self._spatial_repository.list_for_chunks(job_id, chunk_ids)
        process_mentions = self._process_repository.list_for_chunks(job_id, chunk_ids)
        relationships = self._relationship_repository.list_for_chunks(job_id, chunk_ids)
        scores = self._score_repository.get_for_chunks(job_id, chunk_ids)

        entities_by_chunk = _group_entities_by_chunk(entities, chunk_ids)
        temporal_by_chunk = _group_by_chunk(temporal_mentions)
        spatial_by_chunk = _group_by_chunk(spatial_mentions)
        process_by_chunk = _group_by_chunk(process_mentions)
        relationships_by_chunk = _group_relationships_by_chunk(relationships, chunk_ids)

        bundles: dict[str, DiscoveryChunkBundle] = {}
        for chunk_id in chunk_ids:
            enrichment_bundle = enrichment_bundles.get(chunk_id)
            enrichment = enrichment_bundle.enrichment if enrichment_bundle else None
            bundles[chunk_id] = DiscoveryChunkBundle(
                chunk_id=chunk_id,
                language_code=enrichment.language_code if enrichment else None,
                enrichment=enrichment,
                keywords=enrichment_bundle.keywords if enrichment_bundle else (),
                topics=enrichment_bundle.topics if enrichment_bundle else (),
                entities=tuple(entities_by_chunk.get(chunk_id, [])),
                entity_mentions=tuple(mentions_by_chunk.get(chunk_id, [])),
                temporal_mentions=tuple(temporal_by_chunk.get(chunk_id, [])),
                spatial_mentions=tuple(spatial_by_chunk.get(chunk_id, [])),
                process_mentions=tuple(process_by_chunk.get(chunk_id, [])),
                relationships=tuple(relationships_by_chunk.get(chunk_id, [])),
                score=scores.get(chunk_id),
            )
        return bundles


def _group_by_chunk(rows: Iterable) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row.chunk_id, []).append(row)
    return grouped


def _group_entities_by_chunk(entities: list[KnowledgeEntity], chunk_ids: list[str]) -> dict[str, list[KnowledgeEntity]]:
    chunk_id_set = set(chunk_ids)
    grouped: dict[str, list[KnowledgeEntity]] = {chunk_id: [] for chunk_id in chunk_ids}
    for entity in entities:
        for chunk_id in entity.chunk_ids or []:
            if chunk_id in chunk_id_set:
                grouped.setdefault(chunk_id, []).append(entity)
    return grouped


def _group_relationships_by_chunk(
    relationships: list[KnowledgeRelationship],
    chunk_ids: list[str],
) -> dict[str, list[KnowledgeRelationship]]:
    chunk_id_set = set(chunk_ids)
    grouped: dict[str, list[KnowledgeRelationship]] = {chunk_id: [] for chunk_id in chunk_ids}
    seen: dict[str, set[str]] = {chunk_id: set() for chunk_id in chunk_ids}
    for relationship in relationships:
        related_chunks = set(relationship.evidence_chunk_ids or [])
        if relationship.to_type == "chunk":
            related_chunks.add(relationship.to_id)
        if relationship.from_type == "chunk":
            related_chunks.add(relationship.from_id)
        for chunk_id in related_chunks:
            if chunk_id not in chunk_id_set:
                continue
            if relationship.id in seen[chunk_id]:
                continue
            seen[chunk_id].add(relationship.id)
            grouped[chunk_id].append(relationship)
    return grouped


__all__ = ["DiscoveryBundleRepository", "DiscoveryChunkBundle"]
