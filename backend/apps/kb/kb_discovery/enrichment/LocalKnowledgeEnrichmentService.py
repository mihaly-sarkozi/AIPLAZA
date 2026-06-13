from __future__ import annotations

from collections import Counter

from apps.kb.kb_discovery.content_types.ContentTypeDetectionService import ContentTypeDetectionService
from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.DiscoveryJobContext import DiscoveryJobContext
from apps.kb.kb_discovery.dto.DiscoveryResultDtos import DiscoveryWarning, LocalKnowledgeEnrichmentResult
from apps.kb.kb_discovery.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_discovery.enrichment.chunk_metadata_boost import chunk_metadata_boost
from apps.kb.kb_discovery.enrichment.chunk_profile import lead_sentence, preview_text
from apps.kb.kb_discovery.enrichment.entity_signals import entity_signals
from apps.kb.kb_discovery.enrichment.language_resolver import resolve_chunk_language
from apps.kb.kb_discovery.enums.SupportedLanguage import SupportedLanguage
from apps.kb.kb_discovery.keywords.KeywordExtractionService import KeywordExtractionService
from apps.kb.kb_discovery.mapper.discovery_mapper import keyword_dto_to_orm, topic_dto_to_orm
from apps.kb.kb_discovery.mapper.enrichment_mapper import enrichment_dto_to_orm
from apps.kb.kb_discovery.repository.EnrichmentRepository import EnrichmentRepository
from apps.kb.kb_discovery.repository.EntityRepository import EntityMentionRepository
from apps.kb.kb_discovery.repository.KeywordRepository import KeywordRepository
from apps.kb.kb_discovery.repository.TopicRepository import TopicRepository
from apps.kb.kb_discovery.topics.TopicDetectionService import TopicDetectionService
from apps.kb.kb_processing.enums.ProcessingIssueCode import ProcessingIssueCode
from apps.kb.kb_processing.enums.ProcessingIssueSeverity import ProcessingIssueSeverity
from apps.kb.shared.ports.processing_flow_recorder import (
    NoOpProcessingFlowRecorder,
    ProcessingFlowContext,
    ProcessingFlowRecorder,
)


class LocalKnowledgeEnrichmentService:
    _MIN_TEXT_FOR_KEYWORDS = 100

    def __init__(
        self,
        enrichment_repository: EnrichmentRepository,
        keyword_repository: KeywordRepository,
        topic_repository: TopicRepository,
        mention_repository: EntityMentionRepository | None = None,
        *,
        keyword_service: KeywordExtractionService | None = None,
        topic_service: TopicDetectionService | None = None,
        content_type_service: ContentTypeDetectionService | None = None,
        flow_recorder: ProcessingFlowRecorder | None = None,
    ) -> None:
        self._enrichment_repository = enrichment_repository
        self._keyword_repository = keyword_repository
        self._topic_repository = topic_repository
        self._mention_repository = mention_repository
        self._keywords = keyword_service or KeywordExtractionService()
        self._topics = topic_service or TopicDetectionService()
        self._content_types = content_type_service or ContentTypeDetectionService()
        self._flow_recorder = flow_recorder or NoOpProcessingFlowRecorder()

    def run(self, ctx: DiscoveryJobContext, chunks: list[DiscoveryChunkDto]) -> LocalKnowledgeEnrichmentResult:
        mentions_by_chunk = self._load_mentions(ctx.job_id)
        enrichments: list[KnowledgeEnrichmentDto] = []
        keyword_dtos = []
        topic_dtos = []
        keyword_rows = []
        topic_rows = []
        content_type_distribution: Counter[str] = Counter()
        language_distribution: Counter[str] = Counter()
        fallback_language_chunks = 0
        low_confidence_chunks: list[str] = []
        warnings: list[DiscoveryWarning] = []

        for chunk in chunks:
            language_code, used_fallback = self._resolve_language(chunk, ctx)
            if used_fallback:
                fallback_language_chunks += 1
                warnings.append(
                    DiscoveryWarning(
                        code=ProcessingIssueCode.MISSING_CHUNK_LANGUAGE_FOR_ENRICHMENT.value,
                        chunk_id=chunk.chunk_id,
                    )
                )
                self._open_issue(
                    ctx,
                    chunk,
                    ProcessingIssueCode.MISSING_CHUNK_LANGUAGE_FOR_ENRICHMENT.value,
                )

            mentions = mentions_by_chunk.get(chunk.chunk_id, [])
            chunk_keywords = self._keywords.extract_for_chunk(
                chunk,
                language_code=language_code,
                mentions=mentions,
            )
            keyword_dtos.extend(chunk_keywords)
            keyword_rows.extend(keyword_dto_to_orm(ctx, item) for item in chunk_keywords)

            if len(chunk.text.strip()) > self._MIN_TEXT_FOR_KEYWORDS and not chunk_keywords:
                warnings.append(
                    DiscoveryWarning(
                        code=ProcessingIssueCode.NO_KEYWORDS_EXTRACTED.value,
                        chunk_id=chunk.chunk_id,
                    )
                )
                self._open_issue(ctx, chunk, ProcessingIssueCode.NO_KEYWORDS_EXTRACTED.value)

            chunk_topics = self._topics.detect_for_chunk(
                chunk,
                language_code=language_code,
                keyword_terms=[item.normalized_term for item in chunk_keywords[:10]],
                mentions=mentions,
            )
            topic_dtos.extend(chunk_topics)
            topic_rows.extend(topic_dto_to_orm(ctx, item) for item in chunk_topics)
            if not chunk_topics and len(chunk.text.strip()) > 200:
                warnings.append(
                    DiscoveryWarning(
                        code=ProcessingIssueCode.NO_TOPICS_DETECTED.value,
                        chunk_id=chunk.chunk_id,
                    )
                )
                self._open_issue(ctx, chunk, ProcessingIssueCode.NO_TOPICS_DETECTED.value)

            content_type_result = self._content_types.detect_for_chunk(chunk)
            if content_type_result.content_type == "unknown":
                warnings.append(
                    DiscoveryWarning(
                        code=ProcessingIssueCode.CONTENT_TYPE_UNKNOWN.value,
                        chunk_id=chunk.chunk_id,
                    )
                )
                self._open_issue(ctx, chunk, ProcessingIssueCode.CONTENT_TYPE_UNKNOWN.value)

            profile_confidence = self._profile_confidence(
                chunk,
                chunk_keywords,
                chunk_topics,
                content_type_result.confidence,
                chunk.language_confidence if chunk.language_confidence is not None else ctx.language_confidence,
            )
            if profile_confidence < 0.45:
                low_confidence_chunks.append(chunk.chunk_id)
                warnings.append(
                    DiscoveryWarning(
                        code=ProcessingIssueCode.LOW_ENRICHMENT_CONFIDENCE.value,
                        chunk_id=chunk.chunk_id,
                    )
                )
                self._open_issue(ctx, chunk, ProcessingIssueCode.LOW_ENRICHMENT_CONFIDENCE.value)

            metadata = {
                "keyword_count": len(chunk_keywords),
                "topic_count": len(chunk_topics),
                "entity_count": len(mentions),
                "top_keywords": [item.display_term for item in chunk_keywords[:5]],
                "top_topics": [item.topic_key for item in chunk_topics[:5]],
                "entity_signals": entity_signals(mentions),
                **content_type_result.metadata,
            }
            enrichment = KnowledgeEnrichmentDto(
                chunk_id=chunk.chunk_id,
                lead_sentence=lead_sentence(chunk.text),
                preview_text=preview_text(chunk.text),
                content_type=content_type_result.content_type,
                content_type_confidence=content_type_result.confidence,
                language_code=language_code,
                language_confidence=(
                    chunk.language_confidence
                    if chunk.language_confidence is not None
                    else ctx.language_confidence
                ),
                profile_confidence=profile_confidence,
                metadata=metadata,
            )
            enrichments.append(enrichment)
            content_type_distribution[content_type_result.content_type] += 1
            language_distribution[language_code] += 1

        enrichment_rows = [enrichment_dto_to_orm(ctx, dto) for dto in enrichments]
        self._enrichment_repository.replace_for_job(ctx.job_id, enrichment_rows)
        self._keyword_repository.replace_for_job(ctx.job_id, keyword_rows)
        self._topic_repository.replace_for_job(ctx.job_id, topic_rows)

        trace = {
            "chunks_processed": len(chunks),
            "enrichments_created": len(enrichments),
            "keywords_created": len(keyword_rows),
            "topics_created": len(topic_rows),
            "content_type_distribution": dict(content_type_distribution),
            "language_distribution": dict(language_distribution),
            "fallback_language_chunks": fallback_language_chunks,
            "low_confidence_chunks": len(low_confidence_chunks),
        }
        return LocalKnowledgeEnrichmentResult(
            enrichments=tuple(enrichments),
            keywords=tuple(keyword_dtos),
            topics=tuple(topic_dtos),
            content_type_distribution=dict(content_type_distribution),
            language_distribution=dict(language_distribution),
            low_confidence_chunks=tuple(low_confidence_chunks),
            warnings=tuple(warnings),
            trace=trace,
        )

    def _load_mentions(self, job_id: str) -> dict[str, list]:
        if self._mention_repository is None:
            return {}
        return self._mention_repository.list_by_job_grouped_by_chunk(job_id)

    def _resolve_language(
        self,
        chunk: DiscoveryChunkDto,
        ctx: DiscoveryJobContext,
    ) -> tuple[str, bool]:
        code, used_fallback = resolve_chunk_language(chunk)
        if used_fallback and ctx.language_code not in {
            SupportedLanguage.UNKNOWN.value,
            SupportedLanguage.MIXED.value,
            "",
        }:
            return ctx.language_code, True
        return code, used_fallback

    def _profile_confidence(
        self,
        chunk: DiscoveryChunkDto,
        keywords: list,
        topics: list,
        content_type_confidence: float,
        language_confidence: float,
    ) -> float:
        base = 0.25
        base += min(0.25, len(keywords) * 0.02)
        base += min(0.15, len(topics) * 0.05)
        base += content_type_confidence * 0.2
        base += language_confidence * 0.1
        base += chunk_metadata_boost(chunk)
        return round(max(0.0, min(1.0, base)), 4)

    def _open_issue(self, ctx: DiscoveryJobContext, chunk: DiscoveryChunkDto, issue_code: str) -> None:
        flow_ctx = ProcessingFlowContext(
            tenant_slug=ctx.tenant_slug or "",
            knowledge_base_id=ctx.knowledge_base_id,
            training_batch_id=ctx.training_batch_id,
            training_item_id=ctx.training_item_id,
            job_id=ctx.job_id,
            created_by=ctx.created_by,
        )
        self._flow_recorder.open_issue(
            flow_ctx,
            module="kb_discovery",
            stage="local_knowledge_enrichment",
            step="enrichment",
            severity=ProcessingIssueSeverity.WARNING.value,
            issue_code=issue_code,
            issue_message=f"{issue_code} chunk={chunk.chunk_id}",
            metadata_json={"chunk_id": chunk.chunk_id},
        )


__all__ = ["LocalKnowledgeEnrichmentService"]
