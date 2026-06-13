from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
    source: str = ""
    language_code: str | None = None
    subtype: str | None = None
    metadata: tuple[tuple[str, Any], ...] = ()


__all__ = ["EntityCandidate"]
