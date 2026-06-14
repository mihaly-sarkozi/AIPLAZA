from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiscoveryChecklist:
    has_entities: bool = False
    has_chunks: bool = False
    has_enrichments: bool = False
    has_scores: bool = False
    enrichment_count: int = 0
    score_count: int = 0
    keyword_count: int = 0
    topic_count: int = 0
    entity_mention_count: int = 0
    relationship_count: int = 0
    temporal_count: int = 0
    spatial_count: int = 0
    process_count: int = 0
    missing_chunk_language_count: int = 0
    duplicate_keyword_chunks: int = 0
    duplicate_topic_chunks: int = 0
    process_content_without_extraction: int = 0
    unknown_content_type_ratio: float = 0.0
    topic_coverage_ratio: float = 0.0
    keyword_coverage_ratio: float = 0.0
    low_score_chunks: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)
    missing: tuple[str, ...] = field(default_factory=tuple)

    @property
    def core_complete(self) -> bool:
        return self.has_chunks and self.has_enrichments and self.has_scores


class ValidateDiscoveryResult:
    _UNKNOWN_TYPES = frozenset({"unknown", "general_text"})
    _LOW_SCORE_THRESHOLD = 0.35

    def __call__(
        self,
        *,
        chunk_count: int,
        entity_count: int,
        enrichment_count: int,
        score_count: int,
        keyword_count: int,
        topic_count: int,
        entity_mention_count: int = 0,
        relationship_count: int = 0,
        temporal_count: int = 0,
        spatial_count: int = 0,
        process_count: int = 0,
        missing_chunk_language_count: int = 0,
        content_type_counts: dict[str, int] | None = None,
        chunks_with_topics: int = 0,
        chunks_with_keywords: int = 0,
        long_text_chunks: int = 0,
        duplicate_keyword_chunks: int = 0,
        duplicate_topic_chunks: int = 0,
        process_content_without_extraction: int = 0,
        low_score_chunks: int = 0,
        entity_relationship_count: int = 0,
        topic_relationship_count: int = 0,
        temporal_relationship_count: int = 0,
        spatial_relationship_count: int = 0,
        process_relationship_count: int = 0,
        scores: list | None = None,
    ) -> DiscoveryChecklist:
        checks = {
            "chunks": chunk_count > 0,
            "enrichments": enrichment_count == chunk_count and chunk_count > 0,
            "scores": score_count == chunk_count and chunk_count > 0,
        }
        missing = tuple(name for name, passed in checks.items() if not passed)
        warnings: list[str] = []

        if missing_chunk_language_count > 0:
            warnings.append("MISSING_CHUNK_LANGUAGE")
        if keyword_count == 0 and long_text_chunks > 0:
            warnings.append("LOW_KEYWORD_COVERAGE")
        if chunks_with_topics == 0 and long_text_chunks > 0:
            warnings.append("LOW_TOPIC_COVERAGE")
        if duplicate_keyword_chunks > 0:
            warnings.append("DUPLICATE_KEYWORDS")
        if duplicate_topic_chunks > 0:
            warnings.append("DUPLICATE_TOPICS")
        if entity_mention_count > 0 and entity_relationship_count == 0:
            warnings.append("MISSING_ENTITY_RELATIONSHIPS")
        if topic_count > 0 and topic_relationship_count == 0:
            warnings.append("MISSING_TOPIC_RELATIONSHIPS")
        if temporal_count > 0 and temporal_relationship_count == 0:
            warnings.append("MISSING_TEMPORAL_RELATIONSHIPS")
        if spatial_count > 0 and spatial_relationship_count == 0:
            warnings.append("MISSING_SPATIAL_RELATIONSHIPS")
        if process_count > 0 and process_relationship_count == 0:
            warnings.append("MISSING_PROCESS_RELATIONSHIPS")
        if process_content_without_extraction > 0:
            warnings.append("PROCESS_CONTENT_WITHOUT_PROCESS_EXTRACTION")
        if low_score_chunks > 0:
            warnings.append("LOW_DISCOVERY_SCORE")

        content_type_counts = content_type_counts or {}
        unknown_ratio = 0.0
        if chunk_count:
            unknown_count = sum(content_type_counts.get(name, 0) for name in self._UNKNOWN_TYPES)
            unknown_ratio = unknown_count / chunk_count
            if unknown_ratio > 0.4:
                warnings.append("HIGH_UNKNOWN_CONTENT_TYPE_RATIO")

        topic_coverage = chunks_with_topics / chunk_count if chunk_count else 0.0
        if topic_coverage < 0.3 and long_text_chunks > 0:
            avg_long = long_text_chunks / max(chunk_count, 1)
            if avg_long > 0.7:
                warnings.append("LOW_TOPIC_COVERAGE")

        keyword_coverage = chunks_with_keywords / chunk_count if chunk_count else 0.0
        if keyword_coverage < 0.3 and long_text_chunks > 0:
            warnings.append("LOW_KEYWORD_COVERAGE")

        if score_count < chunk_count:
            warnings.append("MISSING_SCORE")

        return DiscoveryChecklist(
            has_entities=entity_count > 0,
            has_chunks=checks["chunks"],
            has_enrichments=checks["enrichments"],
            has_scores=checks["scores"],
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
            duplicate_keyword_chunks=duplicate_keyword_chunks,
            duplicate_topic_chunks=duplicate_topic_chunks,
            process_content_without_extraction=process_content_without_extraction,
            unknown_content_type_ratio=round(unknown_ratio, 4),
            topic_coverage_ratio=round(topic_coverage, 4),
            keyword_coverage_ratio=round(keyword_coverage, 4),
            low_score_chunks=low_score_chunks,
            warnings=tuple(dict.fromkeys(warnings)),
            missing=missing,
        )


__all__ = ["DiscoveryChecklist", "ValidateDiscoveryResult"]
