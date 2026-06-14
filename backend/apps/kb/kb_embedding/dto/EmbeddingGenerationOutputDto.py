from __future__ import annotations

from dataclasses import dataclass, field

from apps.kb.kb_embedding.dto.EmbeddingResultDto import EmbeddingResultDto


@dataclass(frozen=True)
class EmbeddingGenerationFailureDto:
    chunk_id: str
    error_code: str
    error_message: str


@dataclass
class EmbeddingGenerationOutputDto:
    results: list[EmbeddingResultDto] = field(default_factory=list)
    failures: list[EmbeddingGenerationFailureDto] = field(default_factory=list)


__all__ = ["EmbeddingGenerationFailureDto", "EmbeddingGenerationOutputDto"]
