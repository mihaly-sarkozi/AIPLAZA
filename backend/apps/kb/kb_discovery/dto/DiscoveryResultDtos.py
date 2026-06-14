from __future__ import annotations

from dataclasses import dataclass, field

from apps.kb.kb_discovery.dto.DiscoveryChunkDto import DiscoveryChunkDto
from apps.kb.kb_discovery.dto.KnowledgeEnrichmentDto import KnowledgeEnrichmentDto
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import EntityMentionDto, KnowledgeEntityDto


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
    language_code: str = "unknown"
    recognizer_name: str = ""
    start_offset: int | None = None
    end_offset: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SpatialMentionDto:
    chunk_id: str
    raw_text: str
    normalized_location: str
    location_type: str
    confidence: float
    language_code: str = "unknown"
    recognizer_name: str = ""
    start_offset: int | None = None
    end_offset: int | None = None
    site_id: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessMentionDto:
    chunk_id: str
    process_name: str
    step_text: str
    step_order: int | None = None
    responsibility: str | None = None
    input_hint: str | None = None
    output_hint: str | None = None
    is_required: bool = True
    is_optional: bool = False
    confidence: float = 0.0
    language_code: str = "unknown"
    recognizer_name: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ProcessExtractionResult:
    mentions: tuple[ProcessMentionDto, ...] = ()
    trace: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TemporalExtractionResult:
    mentions: tuple[TemporalMentionDto, ...] = ()
    trace: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SpatialExtractionResult:
    mentions: tuple[SpatialMentionDto, ...] = ()
    trace: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RelationshipBuildInput:
    chunks: tuple[DiscoveryChunkDto, ...] = ()
    entities: tuple[KnowledgeEntityDto, ...] = ()
    mentions: tuple[EntityMentionDto, ...] = ()
    enrichments: tuple[KnowledgeEnrichmentDto, ...] = ()
    keywords: tuple[KnowledgeKeywordDto, ...] = ()
    topics: tuple[KnowledgeTopicDto, ...] = ()
    temporal_mentions: tuple[TemporalMentionDto, ...] = ()
    spatial_mentions: tuple[SpatialMentionDto, ...] = ()
    process_mentions: tuple[ProcessMentionDto, ...] = ()


@dataclass(frozen=True)
class RelationshipBuildResult:
    relationship_count: int = 0
    trace: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class KnowledgeScoringInput:
    chunks: tuple[DiscoveryChunkDto, ...] = ()
    enrichments: tuple[KnowledgeEnrichmentDto, ...] = ()
    keywords: tuple[KnowledgeKeywordDto, ...] = ()
    topics: tuple[KnowledgeTopicDto, ...] = ()
    entities: tuple[KnowledgeEntityDto, ...] = ()
    entity_mentions: tuple[EntityMentionDto, ...] = ()
    temporal_mentions: tuple[TemporalMentionDto, ...] = ()
    spatial_mentions: tuple[SpatialMentionDto, ...] = ()
    process_mentions: tuple[ProcessMentionDto, ...] = ()
    relationship_count: int = 0


@dataclass(frozen=True)
class DiscoveryWarning:
    code: str
    chunk_id: str | None = None
    message: str = ""


@dataclass(frozen=True)
class LocalKnowledgeEnrichmentResult:
    enrichments: tuple[KnowledgeEnrichmentDto, ...]
    keywords: tuple[KnowledgeKeywordDto, ...] = ()
    topics: tuple[KnowledgeTopicDto, ...] = ()
    content_type_distribution: dict[str, int] = field(default_factory=dict)
    language_distribution: dict[str, int] = field(default_factory=dict)
    low_confidence_chunks: tuple[str, ...] = ()
    warnings: tuple[DiscoveryWarning, ...] = ()
    trace: dict[str, object] = field(default_factory=dict)


EnrichmentRunResult = LocalKnowledgeEnrichmentResult


@dataclass(frozen=True)
class KnowledgeScoreDto:
    chunk_id: str
    knowledge_score: float
    components: dict[str, float]


__all__ = [
    "DiscoveryWarning",
    "EnrichmentRunResult",
    "KnowledgeKeywordDto",
    "KnowledgeScoreDto",
    "KnowledgeScoringInput",
    "KnowledgeTopicDto",
    "LocalKnowledgeEnrichmentResult",
    "ProcessExtractionResult",
    "ProcessMentionDto",
    "RelationshipBuildInput",
    "RelationshipBuildResult",
    "SpatialExtractionResult",
    "SpatialMentionDto",
    "TemporalExtractionResult",
    "TemporalMentionDto",
]
