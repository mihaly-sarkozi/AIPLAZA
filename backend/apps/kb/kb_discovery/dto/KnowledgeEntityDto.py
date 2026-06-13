from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    source: str = ""
    language_code: str | None = None
    subtype: str | None = None
    recognizer_name: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    page_numbers: tuple[int, ...] = field(default_factory=tuple)
    source_part_ids: tuple[str, ...] = field(default_factory=tuple)


__all__ = ["EntityMentionDto", "KnowledgeEntityDto"]
