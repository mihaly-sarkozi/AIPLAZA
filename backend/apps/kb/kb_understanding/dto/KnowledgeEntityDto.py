from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/KnowledgeEntityDto.py
# Feladat: Az entity extraction lépés kimenete — egy felismert entitás.
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass, field

from apps.kb.kb_understanding.enums.EntityType import EntityType


@dataclass(frozen=True)
class KnowledgeEntityDto:
    entity_type: EntityType
    name: str
    normalized_name: str
    confidence: float
    aliases: tuple[str, ...] = field(default_factory=tuple)
    chunk_ids: tuple[str, ...] = field(default_factory=tuple)


__all__ = ["KnowledgeEntityDto"]
