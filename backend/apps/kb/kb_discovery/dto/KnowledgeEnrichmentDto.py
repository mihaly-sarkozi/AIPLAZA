from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeEnrichmentDto:
    chunk_id: str
    lead_sentence: str = ""
    keywords: tuple[str, ...] = field(default_factory=tuple)
    topics: tuple[str, ...] = field(default_factory=tuple)
    content_type: str | None = None
    language_code: str | None = None
    language_confidence: float = 0.0
    possible_questions: tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.0


__all__ = ["KnowledgeEnrichmentDto"]
