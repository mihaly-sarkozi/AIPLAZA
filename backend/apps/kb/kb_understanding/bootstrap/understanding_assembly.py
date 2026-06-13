from __future__ import annotations

from dataclasses import dataclass

from apps.kb.kb_understanding.adapters.DocxExtractorAdapter import DocxExtractorAdapter
from apps.kb.kb_understanding.adapters.ManualTextExtractorAdapter import ManualTextExtractorAdapter
from apps.kb.kb_understanding.adapters.OcrExtractorAdapter import OcrExtractorAdapter
from apps.kb.kb_understanding.adapters.PdfExtractorAdapter import PdfExtractorAdapter
from apps.kb.kb_understanding.config.ExtractConfig import DEFAULT_EXTRACT_CONFIG
from apps.kb.kb_understanding.ports.IngestItemReaderInterface import IngestItemReaderInterface
from apps.kb.kb_understanding.repository.ChunkRepository import ChunkRepository
from apps.kb.kb_understanding.repository.ContentRepository import ContentRepository
from apps.kb.kb_understanding.repository.StructureRepository import StructureRepository
from apps.kb.kb_understanding.repository.UnderstandingJobRepository import (
    UnderstandingJobRepository,
)
from apps.kb.kb_understanding.repository.UnderstandingStepRunRepository import (
    UnderstandingStepRunRepository,
)
from apps.kb.kb_understanding.service.ChunkContentService import ChunkContentService
from apps.kb.kb_understanding.service.DetectStructureService import DetectStructureService
from apps.kb.kb_understanding.service.ExtractContentService import ExtractContentService
from apps.kb.kb_understanding.service.NormalizeContentService import NormalizeContentService
from apps.kb.kb_understanding.service.ProcessingTraceService import ProcessingTraceService
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
    start_service: StartUnderstandingService
    pipeline: UnderstandingPipelineService


def build_understanding_services(
    *,
    session_factory,
    file_storage,
    item_reader: IngestItemReaderInterface,
) -> UnderstandingServices:
    job_repository = UnderstandingJobRepository(session_factory)
    step_run_repository = UnderstandingStepRunRepository(session_factory)
    content_repository = ContentRepository(session_factory)
    structure_repository = StructureRepository(session_factory)
    chunk_repository = ChunkRepository(session_factory)

    trace = ProcessingTraceService(step_run_repository)
    extract_config = DEFAULT_EXTRACT_CONFIG
    ocr_extractor = OcrExtractorAdapter(extract_config)
    pipeline = UnderstandingPipelineService(
        job_repository,
        trace,
        extract_service=ExtractContentService(
            content_repository,
            file_storage,
            pdf_extractor=PdfExtractorAdapter(config=extract_config, ocr_extractor=ocr_extractor),
            docx_extractor=DocxExtractorAdapter(config=extract_config),
            text_extractor=ManualTextExtractorAdapter(config=extract_config),
            job_repository=job_repository,
            config=extract_config,
        ),
        normalize_service=NormalizeContentService(content_repository),
        structure_service=DetectStructureService(structure_repository),
        chunk_service=ChunkContentService(chunk_repository),
        validate_service=ValidateUnderstandingService(content_repository, chunk_repository),
    )
    return UnderstandingServices(
        job_repository=job_repository,
        step_run_repository=step_run_repository,
        chunk_repository=chunk_repository,
        start_service=StartUnderstandingService(job_repository, item_reader),
        pipeline=pipeline,
    )


__all__ = ["UnderstandingServices", "build_understanding_services"]
