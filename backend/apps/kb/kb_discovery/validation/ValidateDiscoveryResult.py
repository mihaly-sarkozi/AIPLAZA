from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DiscoveryChecklist:
    has_entities: bool = False
    has_chunks: bool = False
    has_enrichments: bool = False
    enrichment_count: int = 0
    keyword_count: int = 0
    topic_count: int = 0
    missing_chunk_language_count: int = 0
    unknown_content_type_ratio: float = 0.0
    topic_coverage_ratio: float = 0.0
    warnings: tuple[str, ...] = field(default_factory=tuple)
    missing: tuple[str, ...] = field(default_factory=tuple)

    @property
    def core_complete(self) -> bool:
        return self.has_chunks and self.has_enrichments


class ValidateDiscoveryResult:
    _UNKNOWN_TYPES = frozenset({"unknown", "general_text"})

    def __call__(
        self,
        *,
        chunk_count: int,
        entity_count: int,
        enrichment_count: int,
        keyword_count: int,
        topic_count: int,
        missing_chunk_language_count: int = 0,
        content_type_counts: dict[str, int] | None = None,
        chunks_with_topics: int = 0,
        long_text_chunks: int = 0,
    ) -> DiscoveryChecklist:
        checks = {
            "chunks": chunk_count > 0,
            "enrichments": enrichment_count == chunk_count and chunk_count > 0,
        }
        missing = tuple(name for name, passed in checks.items() if not passed)
        warnings: list[str] = []
        if missing_chunk_language_count > 0:
            warnings.append("MISSING_CHUNK_LANGUAGE_FOR_ENRICHMENT")
        if keyword_count == 0 and long_text_chunks > 0:
            warnings.append("NO_KEYWORDS_EXTRACTED")
        if chunks_with_topics == 0 and long_text_chunks > 0:
            warnings.append("NO_TOPICS_DETECTED")

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

        return DiscoveryChecklist(
            has_entities=entity_count > 0,
            has_chunks=checks["chunks"],
            has_enrichments=checks["enrichments"],
            enrichment_count=enrichment_count,
            keyword_count=keyword_count,
            topic_count=topic_count,
            missing_chunk_language_count=missing_chunk_language_count,
            unknown_content_type_ratio=round(unknown_ratio, 4),
            topic_coverage_ratio=round(topic_coverage, 4),
            warnings=tuple(dict.fromkeys(warnings)),
            missing=missing,
        )


__all__ = ["DiscoveryChecklist", "ValidateDiscoveryResult"]
