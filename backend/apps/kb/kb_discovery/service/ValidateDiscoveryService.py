from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.KnowledgeEnrichmentDto import EnrichmentRunResult
from apps.kb.kb_discovery.enums.DiscoveryStatus import DiscoveryStatus
from apps.kb.kb_discovery.repository.EnrichmentRepository import EnrichmentRepository
from apps.kb.kb_discovery.repository.EntityRepository import EntityRepository
from apps.kb.kb_discovery.repository.KeywordRepository import KeywordRepository
from apps.kb.kb_discovery.repository.TopicRepository import TopicRepository
from apps.kb.kb_discovery.validation.ValidateDiscoveryResult import ValidateDiscoveryResult


class ValidateDiscoveryService:
    def __init__(
        self,
        entity_repository: EntityRepository,
        enrichment_repository: EnrichmentRepository,
        keyword_repository: KeywordRepository,
        topic_repository: TopicRepository,
    ) -> None:
        self._entity_repository = entity_repository
        self._enrichment_repository = enrichment_repository
        self._keyword_repository = keyword_repository
        self._topic_repository = topic_repository
        self._validate = ValidateDiscoveryResult()

    def run(
        self,
        ctx: DiscoveryJobContext,
        *,
        chunks: list[DiscoveryChunkDto],
        chunk_count: int,
        enrichment_result: EnrichmentRunResult | None = None,
        had_optional_failures: bool = False,
    ) -> tuple[DiscoveryStatus, object]:
        entity_count = self._entity_repository.count_for_document(ctx.training_item_id)
        enrichment_count = self._enrichment_repository.count_for_job(ctx.job_id)
        keyword_count = self._keyword_repository.count_for_job(ctx.job_id)
        topic_count = self._topic_repository.count_for_job(ctx.job_id)
        missing_chunk_language_count = sum(
            1 for chunk in chunks if not (chunk.language_code or "").strip()
        )
        content_type_counts: dict[str, int] = {}
        chunks_with_topics = 0
        long_text_chunks = 0
        if enrichment_result is not None:
            for enrichment in enrichment_result.enrichments:
                content_type_counts[enrichment.content_type] = (
                    content_type_counts.get(enrichment.content_type, 0) + 1
                )
                if enrichment.metadata.get("topic_count", 0):
                    chunks_with_topics += 1
        for chunk in chunks:
            if len(chunk.text.strip()) > 200:
                long_text_chunks += 1

        checklist = self._validate(
            chunk_count=chunk_count,
            entity_count=entity_count,
            enrichment_count=enrichment_count,
            keyword_count=keyword_count,
            topic_count=topic_count,
            missing_chunk_language_count=missing_chunk_language_count,
            content_type_counts=content_type_counts,
            chunks_with_topics=chunks_with_topics,
            long_text_chunks=long_text_chunks,
        )
        if not checklist.core_complete:
            return DiscoveryStatus.FAILED, checklist
        if had_optional_failures or checklist.warnings:
            return DiscoveryStatus.PARTIAL, checklist
        return DiscoveryStatus.READY_FOR_EMBEDDING, checklist


__all__ = ["ValidateDiscoveryService"]
