from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_discovery.entities.ExtractEntitiesService import ExtractEntitiesService
from apps.kb.kb_discovery.enrichment.LocalKnowledgeEnrichmentService import LocalKnowledgeEnrichmentService
from apps.kb.kb_discovery.relationships.BuildRelationshipsService import BuildRelationshipsService
from apps.kb.kb_discovery.repository.DiscoveryJobRepository import DiscoveryJobRepository
from apps.kb.kb_discovery.repository.DiscoveryStepRunRepository import DiscoveryStepRunRepository
from apps.kb.kb_discovery.repository.EnrichmentRepository import EnrichmentRepository
from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository
from apps.kb.kb_discovery.repository.KeywordRepository import KeywordRepository
from apps.kb.kb_discovery.repository.RelationshipRepository import RelationshipRepository
from apps.kb.kb_discovery.repository.ScoreRepository import ScoreRepository
from apps.kb.kb_discovery.repository.TopicRepository import TopicRepository
from apps.kb.kb_discovery.scoring.ScoreKnowledgeService import ScoreKnowledgeService
from apps.kb.kb_discovery.service.DiscoveryPipelineService import DiscoveryPipelineService
from apps.kb.kb_discovery.service.DiscoveryTraceService import DiscoveryTraceService
from apps.kb.kb_discovery.service.LanguageDetectionService import LanguageDetectionService
from apps.kb.kb_discovery.service.StartDiscoveryService import StartDiscoveryService
from apps.kb.kb_discovery.service.ValidateDiscoveryService import ValidateDiscoveryService
from apps.kb.kb_discovery.ports.ChunkReaderPort import ChunkReaderPort, UnderstandingJobReaderPort


@dataclass(frozen=True)
class DiscoveryServices:
    job_repository: DiscoveryJobRepository
    start_service: StartDiscoveryService
    pipeline: DiscoveryPipelineService


def build_discovery_services(
    *,
    session_factory,
    chunk_reader: ChunkReaderPort,
    understanding_job_reader: UnderstandingJobReaderPort | None = None,
    person_directory=None,
) -> DiscoveryServices:
    job_repository = DiscoveryJobRepository(session_factory)
    step_run_repository = DiscoveryStepRunRepository(session_factory)
    entity_repository = EntityRepository(session_factory)
    mention_repository = EntityMentionRepository(session_factory)
    enrichment_repository = EnrichmentRepository(session_factory)
    keyword_repository = KeywordRepository(session_factory)
    topic_repository = TopicRepository(session_factory)
    relationship_repository = RelationshipRepository(session_factory)
    score_repository = ScoreRepository(session_factory)

    trace = DiscoveryTraceService(step_run_repository)
    pipeline = DiscoveryPipelineService(
        job_repository,
        trace,
        language_service=LanguageDetectionService(job_repository),
        entity_service=ExtractEntitiesService(
            entity_repository,
            mention_repository,
            person_directory=person_directory,
        ),
        enrichment_service=LocalKnowledgeEnrichmentService(
            enrichment_repository,
            keyword_repository,
            topic_repository,
        ),
        relationship_service=BuildRelationshipsService(relationship_repository),
        scoring_service=ScoreKnowledgeService(score_repository),
        validate_service=ValidateDiscoveryService(entity_repository),
    )
    return DiscoveryServices(
        job_repository=job_repository,
        start_service=StartDiscoveryService(
            job_repository,
            chunk_reader,
            understanding_job_reader=understanding_job_reader,
        ),
        pipeline=pipeline,
    )


__all__ = ["DiscoveryServices", "build_discovery_services"]
