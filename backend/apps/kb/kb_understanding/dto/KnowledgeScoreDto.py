from __future__ import annotations

# backend/apps/kb/kb_understanding/dto/KnowledgeScoreDto.py
# Feladat: A scoring lépés kimenete — egy chunk minőségi pontszáma.
# Sárközi Mihály - 2026.06.11

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeScoreDto:
    chunk_id: str
    knowledge_score: float
    components: dict[str, float] = field(default_factory=dict)


__all__ = ["KnowledgeScoreDto"]
