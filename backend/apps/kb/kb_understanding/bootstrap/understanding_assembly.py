from __future__ import annotations

# backend/apps/kb/kb_understanding/bootstrap/understanding_assembly.py
# Feladat: A megértési modul teljes service-gráfjának összeszerelése egy helyen —
# a module.py (web container) és a worker handler is ezt használja.
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass

from apps.kb.kb_understanding.adapters.DocxExtractorAdapter import DocxExtractorAdapter
from apps.kb.kb_understanding.adapters.EntityExtractorAdapter import EntityExtractorAdapter
from apps.kb.kb_understanding.adapters.LlmCompletionAdapter import LlmCompletionAdapter
from apps.kb.kb_understanding.adapters.LlmEnrichmentAdapter import LlmEnrichmentAdapter
from apps.kb.kb_understanding.adapters.LocalEmbedder import LocalEmbedder
from apps.kb.kb_understanding.adapters.ManualTextExtractorAdapter import ManualTextExtractorAdapter
from apps.kb.kb_understanding.adapters.PdfExtractorAdapter import PdfExtractorAdapter
from apps.kb.kb_understanding.ports.EmbeddingProviderInterface import EmbeddingProviderInterface
from apps.kb.kb_understanding.ports.EnrichmentInterface import EnrichmentInterface
from apps.kb.kb_understanding.ports.EntityExtractorInterface import EntityExtractorInterface
from apps.kb.kb_understanding.ports.IngestItemReaderInterface import IngestItemReaderInterface
from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository
from apps.kb.kb_understanding.repository.EmbeddingRepository import EmbeddingRepository
from apps.kb.kb_understanding.repository.EnrichmentRepository import EnrichmentRepository
from apps.kb.kb_understanding.repository.EntityRepository import EntityRepository
from apps.kb.kb_understanding.repository.RelationshipRepository import RelationshipRepository
from apps.kb.kb_understanding.repository.ScoreRepository import ScoreRepository
from apps.kb.kb_understanding.repository.StructureRepository import StructureRepository
from apps.kb.kb_understanding.repository.UnderstandingJobRepository import (
    UnderstandingJobRepository,
)
from apps.kb.kb_understanding.repository.UnderstandingStepRunRepository import (
    UnderstandingStepRunRepository,
)
from apps.kb.kb_understanding.service.BuildRelationshipsService import BuildRelationshipsService
from apps.kb.kb_understanding.service.ChunkContentService import ChunkContentService
from apps.kb.kb_understanding.service.DetectStructureService import DetectStructureService
from apps.kb.kb_understanding.service.EmbedChunksService import EmbedChunksService
from apps.kb.kb_understanding.service.EnrichKnowledgeService import EnrichKnowledgeService
from apps.kb.kb_understanding.service.ExtractContentService import ExtractContentService
from apps.kb.kb_understanding.service.ExtractEntitiesService import ExtractEntitiesService
from apps.kb.kb_understanding.service.NormalizeContentService import NormalizeContentService
from apps.kb.kb_understanding.service.ProcessingTraceService import ProcessingTraceService
from apps.kb.kb_understanding.service.ScoreKnowledgeService import ScoreKnowledgeService
from apps.kb.kb_understanding.service.StartUnderstandingService import StartUnderstandingService
from apps.kb.kb_understanding.service.UnderstandingPipelineService import (
    UnderstandingPipelineService,
)
from apps.kb.kb_understanding.service.ValidateUnderstandingService import (
    ValidateUnderstandingService,
)


@dataclass(frozen=True)
class UnderstandingServices:
    job_repository: UnderstandingJobRepository
    step_run_repository: UnderstandingStepRunRepository
    chunk_repository: ChunkRepository
    entity_repository: EntityRepository
    embedding_repository: EmbeddingRepository
    start_service: StartUnderstandingService
    pipeline: UnderstandingPipelineService


def build_understanding_services(
    *,
    session_factory,
    file_storage,
    item_reader: IngestItemReaderInterface,
    entity_extractor: EntityExtractorInterface | None = None,
    enricher: EnrichmentInterface | None = None,
    embedder: EmbeddingProviderInterface | None = None,
) -> UnderstandingServices:
    job_repository = UnderstandingJobRepository(session_factory)
    step_run_repository = UnderstandingStepRunRepository(session_factory)
    content_repository = ContentRepository(session_factory)
    structure_repository = StructureRepository(session_factory)
    chunk_repository = ChunkRepository(session_factory)
    entity_repository = EntityRepository(session_factory)
    enrichment_repository = EnrichmentRepository(session_factory)
    embedding_repository = EmbeddingRepository(session_factory)
    relationship_repository = RelationshipRepository(session_factory)
    score_repository = ScoreRepository(session_factory)

    llm = LlmCompletionAdapter()
    entity_extractor = entity_extractor or EntityExtractorAdapter(llm)
    enricher = enricher or LlmEnrichmentAdapter(llm)
    embedder = embedder or LocalEmbedder()

    trace = ProcessingTraceService(step_run_repository)
    pipeline = UnderstandingPipelineService(
        job_repository,
        trace,
        extract_service=ExtractContentService(
            content_repository,
            file_storage,
            pdf_extractor=PdfExtractorAdapter(),
            docx_extractor=DocxExtractorAdapter(),
            text_extractor=ManualTextExtractorAdapter(),
        ),
        normalize_service=NormalizeContentService(content_repository),
        structure_service=DetectStructureService(structure_repository),
        chunk_service=ChunkContentService(chunk_repository),
        entities_service=ExtractEntitiesService(entity_repository, entity_extractor),
        enrich_service=EnrichKnowledgeService(enrichment_repository, enricher),
        embed_service=EmbedChunksService(embedding_repository, embedder),
        relationships_service=BuildRelationshipsService(relationship_repository),
        score_service=ScoreKnowledgeService(score_repository),
        validate_service=ValidateUnderstandingService(
            content_repository, chunk_repository, embedding_repository
        ),
    )
    return UnderstandingServices(
        job_repository=job_repository,
        step_run_repository=step_run_repository,
        chunk_repository=chunk_repository,
        entity_repository=entity_repository,
        embedding_repository=embedding_repository,
        start_service=StartUnderstandingService(job_repository, item_reader),
        pipeline=pipeline,
    )


__all__ = ["UnderstandingServices", "build_understanding_services"]
