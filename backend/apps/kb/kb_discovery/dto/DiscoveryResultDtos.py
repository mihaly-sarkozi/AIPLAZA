from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeKeywordDto:
    chunk_id: str
    term: str
    normalized_term: str
    display_term: str
    language_code: str
    rank: int
    score: float
    confidence: float
    source: str
    extractor_version: str
    start_offset: int | None = None
    end_offset: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeTopicDto:
    chunk_id: str
    topic_key: str
    display_name: str
    normalized_topic: str
    language_code: str
    confidence: float
    score: float
    source: str
    taxonomy_version: str
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalMentionDto:
    chunk_id: str
    raw_text: str
    normalized_start: str | None
    normalized_end: str | None
    temporal_type: str
    confidence: float


@dataclass(frozen=True)
class SpatialMentionDto:
    chunk_id: str
    raw_text: str
    normalized_location: str
    location_type: str
    confidence: float
    site_id: str | None = None


@dataclass(frozen=True)
class KnowledgeScoreDto:
    chunk_id: str
    knowledge_score: float
    components: dict[str, float]


__all__ = [
    "KnowledgeKeywordDto",
    "KnowledgeScoreDto",
    "KnowledgeTopicDto",
    "SpatialMentionDto",
    "TemporalMentionDto",
]
