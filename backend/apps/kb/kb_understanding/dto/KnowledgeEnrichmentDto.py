from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/KnowledgeEnrichmentDto.py
# Feladat: Az enrichment lépés kimenete — egy chunk többletmetaadata.
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeEnrichmentDto:
    chunk_id: str
    summary: str = ""
    keywords: tuple[str, ...] = field(default_factory=tuple)
    topics: tuple[str, ...] = field(default_factory=tuple)
    possible_questions: tuple[str, ...] = field(default_factory=tuple)
    content_type: str | None = None
    language: str | None = None
    difficulty: str | None = None
    importance: float = 0.0
    confidence: float = 0.0


__all__ = ["KnowledgeEnrichmentDto"]
