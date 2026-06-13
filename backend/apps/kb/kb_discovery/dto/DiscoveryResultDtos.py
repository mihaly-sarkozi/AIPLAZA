from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeKeywordDto:
    chunk_id: str
    term: str
    rank: int
    score: float


@dataclass(frozen=True)
class KnowledgeTopicDto:
    chunk_id: str
    topic_key: str
    confidence: float


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
