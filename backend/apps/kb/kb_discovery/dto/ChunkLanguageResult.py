from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChunkLanguageResult:
    chunk_id: str
    language_code: str
    language_confidence: float
    language_detected_by: str
    language_metadata: dict = field(default_factory=dict)


__all__ = ["ChunkLanguageResult"]
