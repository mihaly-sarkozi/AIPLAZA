from __future__ import annotations

from dataclasses import dataclass, field

from apps.kb.kb_discovery.enums.EntityType import EntityType


@dataclass(frozen=True)
class EntityCandidate:
    entity_type: EntityType
    name: str
    normalized_name: str
    chunk_id: str
    start_offset: int
    end_offset: int
    confidence: float
    aliases: tuple[str, ...] = field(default_factory=tuple)


__all__ = ["EntityCandidate"]
