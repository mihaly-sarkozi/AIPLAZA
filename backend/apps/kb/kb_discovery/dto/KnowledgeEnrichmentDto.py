from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class KnowledgeEnrichmentDto:
    chunk_id: str
    lead_sentence: str = ""
    preview_text: str = ""
    content_type: str = "general_text"
    content_type_confidence: float = 0.0
    language_code: str = "unknown"
    language_confidence: float = 0.0
    profile_confidence: float = 0.0
    metadata: dict[str, object] = field(default_factory=dict)


__all__ = ["KnowledgeEnrichmentDto"]
