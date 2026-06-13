from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
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

    def get_bundle_for_chunks(self, job_id: str, chunk_ids: list[str]) -> dict[str, DiscoveryChunkBundle]:
        if not chunk_ids:
            return {}

        enrichment_bundles = self._enrichment_repository.get_enrichment_bundle_for_chunks(job_id, chunk_ids)
        process_mentions = self._process_repository.list_for_chunks(job_id, chunk_ids)

        bundles: dict[str, DiscoveryChunkBundle] = {}
        for chunk_id in chunk_ids:
            enrichment_bundle = enrichment_bundles.get(chunk_id)
            bundles[chunk_id] = DiscoveryChunkBundle(
                chunk_id=chunk_id,
                language_code=(
                    enrichment_bundle.enrichment.language_code
                    if enrichment_bundle and enrichment_bundle.enrichment
                    else None
                ),
                enrichment=enrichment_bundle.enrichment if enrichment_bundle else None,
                keywords=enrichment_bundle.keywords if enrichment_bundle else (),
                topics=enrichment_bundle.topics if enrichment_bundle else (),
                process_mentions=tuple(
                    mention for mention in process_mentions if mention.chunk_id == chunk_id
                ),
            )
        return bundles


__all__ = ["DiscoveryBundleRepository", "DiscoveryChunkBundle"]
