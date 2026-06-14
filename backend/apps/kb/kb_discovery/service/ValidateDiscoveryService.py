from __future__ import annotations

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import LocalKnowledgeEnrichmentResult
from apps.kb.kb_discovery.enums.DiscoveryStatus import DiscoveryStatus
from apps.kb.kb_discovery.repository.EnrichmentRepository import EnrichmentRepository
from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository, EntityRepository
from apps.kb.kb_discovery.repository.KeywordRepository import KeywordRepository
from apps.kb.kb_discovery.repository.ProcessRepository import ProcessRepository
from apps.kb.kb_discovery.repository.RelationshipRepository import RelationshipRepository
from apps.kb.kb_discovery.repository.ScoreRepository import ScoreRepository
from apps.kb.kb_discovery.repository.SpatialRepository import SpatialRepository
from apps.kb.kb_discovery.repository.TemporalRepository import TemporalRepository
from apps.kb.kb_discovery.repository.TopicRepository import TopicRepository
from apps.kb.kb_discovery.validation.ValidateDiscoveryResult import ValidateDiscoveryResult


class ValidateDiscoveryService:
    def __init__(
        self,
        entity_repository: EntityRepository,
        mention_repository: EntityMentionRepository,
        enrichment_repository: EnrichmentRepository,
        keyword_repository: KeywordRepository,
        topic_repository: TopicRepository,
        score_repository: ScoreRepository,
        relationship_repository: RelationshipRepository,
        temporal_repository: TemporalRepository,
        spatial_repository: SpatialRepository,
        process_repository: ProcessRepository,
    ) -> None:
        self._entity_repository = entity_repository
        self._mention_repository = mention_repository
        self._enrichment_repository = enrichment_repository
        self._keyword_repository = keyword_repository
        self._topic_repository = topic_repository
        self._score_repository = score_repository
        self._relationship_repository = relationship_repository
        self._temporal_repository = temporal_repository
        self._spatial_repository = spatial_repository
        self._process_repository = process_repository
        self._validate = ValidateDiscoveryResult()

    def run(
        self,
        ctx: DiscoveryJobContext,
        *,
        chunks: list[DiscoveryChunkDto],
        chunk_count: int,
        enrichment_result: LocalKnowledgeEnrichmentResult | None = None,
        had_optional_failures: bool = False,
    ) -> tuple[DiscoveryStatus, object]:
        entity_count = self._entity_repository.count_for_document(ctx.training_item_id)
        enrichment_count = self._enrichment_repository.count_for_job(ctx.job_id)
        keyword_count = self._keyword_repository.count_for_job(ctx.job_id)
        topic_count = self._topic_repository.count_for_job(ctx.job_id)
        score_count = self._score_repository.count_for_job(ctx.job_id)
        relationship_count = self._relationship_repository.count_for_job(ctx.job_id)
        temporal_count = self._temporal_repository.count_for_job(ctx.job_id)
        spatial_count = self._spatial_repository.count_for_job(ctx.job_id)
        process_count = self._process_repository.count_for_job(ctx.job_id)
        entity_mention_count = self._mention_repository.count_for_job(ctx.job_id)

        missing_chunk_language_count = sum(
            1 for chunk in chunks if not (chunk.language_code or "").strip()
        )
        content_type_counts: dict[str, int] = {}
        chunks_with_topics = 0
        chunks_with_keywords = 0
        long_text_chunks = 0
        process_content_without_extraction = 0
        low_score_chunks = 0

        if enrichment_result is not None:
            process_chunks = {
                enrichment.chunk_id
                for enrichment in enrichment_result.enrichments
                if enrichment.content_type == "process"
            }
            for enrichment in enrichment_result.enrichments:
                content_type_counts[enrichment.content_type] = (
                    content_type_counts.get(enrichment.content_type, 0) + 1
                )
                if enrichment.metadata.get("topic_count", 0):
                    chunks_with_topics += 1
                if enrichment.metadata.get("keyword_count", 0):
                    chunks_with_keywords += 1
            if process_chunks and process_count == 0:
                process_content_without_extraction = len(process_chunks)

        duplicate_keyword_chunks, duplicate_topic_chunks = self._duplicate_counts(enrichment_result)
        relationship_counts = self._relationship_repository.count_relationship_groups_for_job(ctx.job_id)

        for chunk in chunks:
            if len(chunk.text.strip()) > 200:
                long_text_chunks += 1

        checklist = self._validate(
            chunk_count=chunk_count,
            entity_count=entity_count,
            enrichment_count=enrichment_count,
            score_count=score_count,
            keyword_count=keyword_count,
            topic_count=topic_count,
            entity_mention_count=entity_mention_count,
            relationship_count=relationship_count,
            temporal_count=temporal_count,
            spatial_count=spatial_count,
            process_count=process_count,
            missing_chunk_language_count=missing_chunk_language_count,
            content_type_counts=content_type_counts,
            chunks_with_topics=chunks_with_topics,
            chunks_with_keywords=chunks_with_keywords,
            long_text_chunks=long_text_chunks,
            duplicate_keyword_chunks=duplicate_keyword_chunks,
            duplicate_topic_chunks=duplicate_topic_chunks,
            process_content_without_extraction=process_content_without_extraction,
            low_score_chunks=low_score_chunks,
            entity_relationship_count=relationship_counts.get("entity", 0),
            topic_relationship_count=relationship_counts.get("topic", 0),
            temporal_relationship_count=relationship_counts.get("time", 0),
            spatial_relationship_count=relationship_counts.get("location", 0),
            process_relationship_count=relationship_counts.get("process", 0),
        )
        if not checklist.core_complete:
            return DiscoveryStatus.FAILED, checklist
        if had_optional_failures or checklist.warnings:
            return DiscoveryStatus.PARTIAL, checklist
        return DiscoveryStatus.READY_FOR_EMBEDDING, checklist

    @staticmethod
    def _duplicate_counts(enrichment_result: LocalKnowledgeEnrichmentResult | None) -> tuple[int, int]:
        if enrichment_result is None:
            return 0, 0
        keyword_dupes = 0
        topic_dupes = 0
        keywords_by_chunk: dict[str, list[str]] = {}
        for keyword in enrichment_result.keywords:
            keywords_by_chunk.setdefault(keyword.chunk_id, []).append(keyword.normalized_term)
        for terms in keywords_by_chunk.values():
            if len(terms) != len(set(terms)):
                keyword_dupes += 1
        topics_by_chunk: dict[str, list[str]] = {}
        for topic in enrichment_result.topics:
            topics_by_chunk.setdefault(topic.chunk_id, []).append(topic.topic_key)
        for keys in topics_by_chunk.values():
            if len(keys) != len(set(keys)):
                topic_dupes += 1
        return keyword_dupes, topic_dupes


__all__ = ["ValidateDiscoveryService"]
