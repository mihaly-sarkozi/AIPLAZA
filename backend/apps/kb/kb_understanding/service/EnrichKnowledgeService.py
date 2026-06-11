from __future__ import annotations

# backend/apps/kb/kb_understanding/service/EnrichKnowledgeService.py
# Feladat: Chunkok AI-enrichmentje az adapter-porton keresztül; chunkonkénti hiba
# nem buktatja a lépést — a sikertelen chunk kimarad (részleges eredmény).
# Sárközi Mihály - 2026.06.11

import logging

from apps.kb.kb_understanding.dto.KnowledgeChunkDto import KnowledgeChunkDto
from apps.kb.kb_understanding.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_understanding.dto.UnderstandingJobContext import UnderstandingJobContext
from apps.kb.kb_understanding.enums.UnderstandingErrorCode import UnderstandingErrorCode
from apps.kb.kb_understanding.errors.UnderstandingProcessingError import UnderstandingProcessingError
from apps.kb.kb_understanding.mapper.enrichment_mapper import enrichment_dto_to_orm
from apps.kb.kb_understanding.ports.EnrichmentInterface import EnrichmentInterface
from apps.kb.kb_understanding.repository.EnrichmentRepository import EnrichmentRepository

logger = logging.getLogger(__name__)


class EnrichKnowledgeService:
    def __init__(
        self,
        enrichment_repository: EnrichmentRepository,
        enricher: EnrichmentInterface,
    ) -> None:
        self._enrichment_repository = enrichment_repository
        self._enricher = enricher

    def run(
        self, ctx: UnderstandingJobContext, chunks: list[KnowledgeChunkDto]
    ) -> list[KnowledgeEnrichmentDto]:
        enrichments: list[KnowledgeEnrichmentDto] = []
        failed = 0
        for chunk in chunks:
            try:
                enrichments.append(self._enricher.enrich_chunk(chunk.chunk_id, chunk.text))
            except Exception:
                failed += 1
                logger.warning(
                    "Enrichment hiba (job=%s chunk=%s)", ctx.job_id, chunk.chunk_id, exc_info=True
                )
        if chunks and not enrichments:
            raise UnderstandingProcessingError(
                UnderstandingErrorCode.ENRICHMENT_FAILED, retryable=True, failed=failed
            )
        self._enrichment_repository.replace_for_chunks(
            [chunk.chunk_id for chunk in chunks],
            [enrichment_dto_to_orm(ctx, enrichment) for enrichment in enrichments],
        )
        return enrichments


__all__ = ["EnrichKnowledgeService"]
