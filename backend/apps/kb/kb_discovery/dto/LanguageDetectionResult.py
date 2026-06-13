from __future__ import annotations

from dataclasses import dataclass, field

from apps.kb.kb_discovery.dto.ChunkLanguageResult import ChunkLanguageResult


@dataclass
class LanguageDetectionResult:
    language_code: str
    language_confidence: float
    chunk_languages: dict[str, str]
    chunks_checked: int = 0
    language_distribution: dict[str, int] = field(default_factory=dict)
    chunk_results: list[ChunkLanguageResult] = field(default_factory=list)


__all__ = ["LanguageDetectionResult"]
