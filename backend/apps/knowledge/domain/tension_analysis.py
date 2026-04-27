from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


TENSION_ENGINE_VERSION = "tension_engine_v1"


@dataclass(frozen=True)
class TensionAnalysis:
    """Rule-based tension analysis for two local knowledge profiles.

    This model only classifies tension. It does not decide merge, persistence,
    conflict resolution, or indexing.
    """

    tension_analysis_id: UUID = field(default_factory=uuid4)

    search_profile_id_a: UUID | None = None
    search_profile_id_b: UUID | None = None
    technical_entity_id_a: UUID | None = None
    technical_entity_id_b: UUID | None = None

    candidate_name_a: str = ""
    candidate_name_b: str = ""

    tension_detected: bool = False
    tension_score: float = 0.0
    tension_band: str = "none"
    tension_type: str = "unrelated"
    tension_reason: str = ""
    tension_reasons: list[str] = field(default_factory=list)
    conflicting_claim_ids: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    builder_version: str = TENSION_ENGINE_VERSION
    created_at: datetime = field(default_factory=_utcnow)


def tension_analysis_to_json_dict(analysis: TensionAnalysis) -> dict[str, Any]:
    return {
        "tension_analysis_id": str(analysis.tension_analysis_id),
        "search_profile_id_a": str(analysis.search_profile_id_a) if analysis.search_profile_id_a is not None else None,
        "search_profile_id_b": str(analysis.search_profile_id_b) if analysis.search_profile_id_b is not None else None,
        "technical_entity_id_a": (
            str(analysis.technical_entity_id_a) if analysis.technical_entity_id_a is not None else None
        ),
        "technical_entity_id_b": (
            str(analysis.technical_entity_id_b) if analysis.technical_entity_id_b is not None else None
        ),
        "candidate_name_a": analysis.candidate_name_a,
        "candidate_name_b": analysis.candidate_name_b,
        "tension_detected": analysis.tension_detected,
        "tension_score": analysis.tension_score,
        "tension_band": analysis.tension_band,
        "tension_type": analysis.tension_type,
        "tension_reason": analysis.tension_reason,
        "tension_reasons": list(analysis.tension_reasons),
        "conflicting_claim_ids": list(analysis.conflicting_claim_ids),
        "evidence": dict(analysis.evidence or {}),
        "builder_version": analysis.builder_version,
        "created_at": analysis.created_at.isoformat(),
    }


__all__ = [
    "TENSION_ENGINE_VERSION",
    "TensionAnalysis",
    "tension_analysis_to_json_dict",
]
