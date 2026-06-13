from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.kb.kb_discovery.dto.DiscoveryResultDtos import (
    KnowledgeKeywordDto,
    KnowledgeScoreDto,
    KnowledgeTopicDto,
    SpatialMentionDto,
    TemporalMentionDto,
)
from apps.kb.kb_discovery.dto.KnowledgeEntityDto import EntityMentionDto, KnowledgeEntityDto


@dataclass
class DiscoveryContext:
    tenant_slug: str | None
    knowledge_base_id: str
    training_item_id: str
    person_directory: list[dict[str, Any]] = field(default_factory=list)
    entity_dictionary: list[dict[str, Any]] = field(default_factory=list)
    site_dictionary: list[dict[str, Any]] = field(default_factory=list)
    dictionary_warnings: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DiscoveryResult:
    entities: list[KnowledgeEntityDto] = field(default_factory=list)
    mentions: list[EntityMentionDto] = field(default_factory=list)
    keywords: list[KnowledgeKeywordDto] = field(default_factory=list)
    topics: list[KnowledgeTopicDto] = field(default_factory=list)
    temporal: list[TemporalMentionDto] = field(default_factory=list)
    spatial: list[SpatialMentionDto] = field(default_factory=list)
    content_types: dict[str, str] = field(default_factory=dict)
    process_steps: dict[str, list[str]] = field(default_factory=dict)
    relationship_count: int = 0
    scores: list[KnowledgeScoreDto] = field(default_factory=list)


__all__ = ["DiscoveryContext", "DiscoveryResult"]
