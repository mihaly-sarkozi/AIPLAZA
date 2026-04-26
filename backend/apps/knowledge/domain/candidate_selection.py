from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


CANDIDATE_SELECTION_BUILDER_VERSION = "candidate_selection_v1"


@dataclass(frozen=True)
class EntityCandidate:
    """Deterministic candidate for later comparison/merge decision.

    This model does not make merge decisions and does not index anything.
    """

    candidate_selection_id: UUID = field(default_factory=uuid4)
    search_profile_id: UUID | None = None
    technical_memory_chunk_id: UUID | None = None
    technical_entity_id: UUID | None = None
    local_entity_id: UUID | None = None

    candidate_entity_id: str = ""
    candidate_name: str = ""
    candidate_type: str = "unknown"
    candidate_source: str = "batch_fallback"
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    builder_version: str = CANDIDATE_SELECTION_BUILDER_VERSION
    created_at: datetime = field(default_factory=_utcnow)


def entity_candidate_to_json_dict(candidate: EntityCandidate) -> dict[str, Any]:
    return {
        "candidate_selection_id": str(candidate.candidate_selection_id),
        "search_profile_id": str(candidate.search_profile_id) if candidate.search_profile_id is not None else None,
        "technical_memory_chunk_id": (
            str(candidate.technical_memory_chunk_id) if candidate.technical_memory_chunk_id is not None else None
        ),
        "technical_entity_id": str(candidate.technical_entity_id) if candidate.technical_entity_id is not None else None,
        "local_entity_id": str(candidate.local_entity_id) if candidate.local_entity_id is not None else None,
        "candidate_entity_id": candidate.candidate_entity_id,
        "candidate_name": candidate.candidate_name,
        "candidate_type": candidate.candidate_type,
        "candidate_source": candidate.candidate_source,
        "score": candidate.score,
        "candidate_score": candidate.score,
        "reasons": list(candidate.reasons),
        "candidate_reason": list(candidate.reasons),
        "evidence": dict(candidate.evidence or {}),
        "builder_version": candidate.builder_version,
        "created_at": candidate.created_at.isoformat(),
    }


__all__ = [
    "CANDIDATE_SELECTION_BUILDER_VERSION",
    "EntityCandidate",
    "entity_candidate_to_json_dict",
]
