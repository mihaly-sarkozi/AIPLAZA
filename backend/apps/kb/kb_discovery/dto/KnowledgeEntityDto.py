from __future__ import annotations

from dataclasses import dataclass, field

from apps.kb.kb_discovery.enums.EntityType import EntityType


@dataclass(frozen=True)
class KnowledgeEntityDto:
    entity_type: EntityType
    name: str
    normalized_name: str
    confidence: float
    aliases: tuple[str, ...] = field(default_factory=tuple)
    chunk_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EntityMentionDto:
    entity_type: EntityType
    chunk_id: str
    raw_text: str
    normalized_name: str
    start_offset: int
    end_offset: int
    confidence: float


__all__ = ["EntityMentionDto", "KnowledgeEntityDto"]
