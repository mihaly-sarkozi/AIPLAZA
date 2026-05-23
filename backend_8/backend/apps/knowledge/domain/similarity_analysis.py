from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


SIMILARITY_ENGINE_VERSION = "similarity_engine_v1"


@dataclass(frozen=True)
class SimilarityAnalysis:
    """Evidence-based similarity analysis for a selected candidate.

    This model only scores and explains similarity. It does not decide merge,
    conflict resolution, or persistence.
    """

    similarity_analysis_id: UUID = field(default_factory=uuid4)
    search_profile_id: UUID | None = None
    technical_memory_chunk_id: UUID | None = None
    technical_entity_id: UUID | None = None
    local_entity_id: UUID | None = None

    candidate_entity_id: str = ""
    candidate_name: str = ""
    candidate_type: str = "unknown"

    total_similarity_score: float = 0.0
    similarity_band: str = "low"
    component_scores: dict[str, float] = field(default_factory=dict)
    similarity_reasons: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    builder_version: str = SIMILARITY_ENGINE_VERSION
    created_at: datetime = field(default_factory=_utcnow)


def similarity_analysis_to_json_dict(analysis: SimilarityAnalysis) -> dict[str, Any]:
    return {
        "similarity_analysis_id": str(analysis.similarity_analysis_id),
        "search_profile_id": str(analysis.search_profile_id) if analysis.search_profile_id is not None else None,
        "technical_memory_chunk_id": (
            str(analysis.technical_memory_chunk_id) if analysis.technical_memory_chunk_id is not None else None
        ),
        "technical_entity_id": str(analysis.technical_entity_id) if analysis.technical_entity_id is not None else None,
        "local_entity_id": str(analysis.local_entity_id) if analysis.local_entity_id is not None else None,
        "candidate_entity_id": analysis.candidate_entity_id,
        "candidate_name": analysis.candidate_name,
        "candidate_type": analysis.candidate_type,
        "similarity_score": analysis.total_similarity_score,
        "total_similarity_score": analysis.total_similarity_score,
        "similarity_band": analysis.similarity_band,
        "component_scores": dict(analysis.component_scores or {}),
        "similarity_reasons": list(analysis.similarity_reasons),
        "reasons": list(analysis.similarity_reasons),
        "evidence": dict(analysis.evidence or {}),
        "builder_version": analysis.builder_version,
        "created_at": analysis.created_at.isoformat(),
    }


__all__ = [
    "SIMILARITY_ENGINE_VERSION",
    "SimilarityAnalysis",
    "similarity_analysis_to_json_dict",
]
