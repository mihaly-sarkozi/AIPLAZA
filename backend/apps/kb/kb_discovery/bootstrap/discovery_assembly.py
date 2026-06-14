from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_discovery.entities.ExtractEntitiesService import ExtractEntitiesService
from apps.kb.kb_discovery.enrichment.LocalKnowledgeEnrichmentService import LocalKnowledgeEnrichmentService
from apps.kb.kb_discovery.processes.ProcessExtractionService import ProcessExtractionService
from apps.kb.kb_discovery.relationships.BuildRelationshipsService import BuildRelationshipsService
from apps.kb.kb_discovery.repository.DiscoveryBundleRepository import DiscoveryBundleRepository
from apps.kb.kb_discovery.repository.DiscoveryJobRepository import DiscoveryJobRepository
from apps.kb.kb_discovery.repository.EnrichmentRepository import EnrichmentRepository
from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository
from apps.kb.kb_discovery.repository.KeywordRepository import KeywordRepository
from apps.kb.kb_discovery.repository.ProcessRepository import ProcessRepository
from apps.kb.kb_discovery.repository.RelationshipRepository import RelationshipRepository
from apps.kb.kb_discovery.repository.ScoreRepository import ScoreRepository
from apps.kb.kb_discovery.repository.SpatialRepository import SpatialRepository
from apps.kb.kb_discovery.repository.TemporalRepository import TemporalRepository
from apps.kb.kb_discovery.repository.TopicRepository import TopicRepository
from apps.kb.kb_discovery.scoring.KnowledgeScoringService import KnowledgeScoringService
from apps.kb.kb_discovery.scoring.ScoreKnowledgeService import ScoreKnowledgeService
from apps.kb.kb_discovery.service.DiscoveryPipelineService import DiscoveryPipelineService
from apps.kb.kb_discovery.service.LanguageDetectionService import LanguageDetectionService
from apps.kb.kb_discovery.service.StartDiscoveryService import StartDiscoveryService
from apps.kb.kb_discovery.service.ValidateDiscoveryService import ValidateDiscoveryService
from apps.kb.kb_discovery.spatial.SpatialExtractionService import SpatialExtractionService
from apps.kb.kb_discovery.temporal.TemporalExtractionService import TemporalExtractionService
from apps.kb.kb_discovery.ports.ChunkLanguageWriterPort import ChunkLanguageWriterPort
from apps.kb.kb_discovery.ports.ChunkReaderPort import ChunkReaderPort, UnderstandingJobReaderPort
from apps.kb.shared.ports.processing_flow_recorder import NoOpProcessingFlowRecorder


@dataclass(frozen=True)
class DiscoveryServices:
    job_repository: DiscoveryJobRepository
    start_service: StartDiscoveryService
    pipeline: DiscoveryPipelineService
    bundle_repository: DiscoveryBundleRepository


def build_discovery_services(
    *,
    session_factory,
    chunk_reader: ChunkReaderPort,
    understanding_job_reader: UnderstandingJobReaderPort | None = None,
    chunk_language_writer: ChunkLanguageWriterPort | None = None,
    person_directory=None,
    flow_recorder=None,
) -> DiscoveryServices:
    job_repository = DiscoveryJobRepository(session_factory)
    entity_repository = EntityRepository(session_factory)
    mention_repository = EntityMentionRepository(session_factory)
    enrichment_repository = EnrichmentRepository(session_factory)
    keyword_repository = KeywordRepository(session_factory)
    topic_repository = TopicRepository(session_factory)
    temporal_repository = TemporalRepository(session_factory)
    spatial_repository = SpatialRepository(session_factory)
    process_repository = ProcessRepository(session_factory)
    relationship_repository = RelationshipRepository(session_factory)
    score_repository = ScoreRepository(session_factory)

    knowledge_scoring = KnowledgeScoringService(score_repository)
    bundle_repository = DiscoveryBundleRepository(
        enrichment_repository,
        entity_repository,
        mention_repository,
        temporal_repository,
        spatial_repository,
        process_repository,
        relationship_repository,
        score_repository,
    )
    pipeline = DiscoveryPipelineService(
        job_repository,
        language_service=LanguageDetectionService(job_repository, chunk_language_writer),
        entity_service=ExtractEntitiesService(
            entity_repository,
            mention_repository,
            person_directory=person_directory,
            flow_recorder=flow_recorder,
        ),
        enrichment_service=LocalKnowledgeEnrichmentService(
            enrichment_repository,
            keyword_repository,
            topic_repository,
            mention_repository,
            flow_recorder=flow_recorder,
        ),
        temporal_service=TemporalExtractionService(temporal_repository),
        spatial_service=SpatialExtractionService(spatial_repository),
        process_service=ProcessExtractionService(process_repository),
        relationship_service=BuildRelationshipsService(relationship_repository),
        scoring_service=ScoreKnowledgeService(knowledge_scoring),
        validate_service=ValidateDiscoveryService(
            entity_repository,
            mention_repository,
            enrichment_repository,
            keyword_repository,
            topic_repository,
            score_repository,
            relationship_repository,
            temporal_repository,
            spatial_repository,
            process_repository,
        ),
        flow_recorder=flow_recorder or NoOpProcessingFlowRecorder(),
    )
    return DiscoveryServices(
        job_repository=job_repository,
        start_service=StartDiscoveryService(
            job_repository,
            chunk_reader,
            understanding_job_reader=understanding_job_reader,
        ),
        pipeline=pipeline,
        bundle_repository=bundle_repository,
    )


__all__ = ["DiscoveryServices", "build_discovery_services"]
