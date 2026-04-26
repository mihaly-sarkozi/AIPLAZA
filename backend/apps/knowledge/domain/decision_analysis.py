from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


DECISION_ENGINE_VERSION = "decision_engine_v1"


@dataclass(frozen=True)
class DecisionAnalysis:
    """Machine decision proposal for a candidate/profile pair.

    This is only a proposal. It does not merge, persist global profiles, index,
    or mutate existing knowledge.
    """

    decision_analysis_id: UUID = field(default_factory=uuid4)
    search_profile_id: UUID | None = None
    technical_entity_id: UUID | None = None
    local_entity_id: UUID | None = None

    candidate_entity_id: str = ""
    candidate_name: str = ""
    candidate_type: str = "unknown"

    decision: str = "needs_review"
    decision_confidence: float = 0.0
    decision_reason: str = ""
    manual_review_required: bool = True
    affected_claim_ids: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    builder_version: str = DECISION_ENGINE_VERSION
    created_at: datetime = field(default_factory=_utcnow)


def decision_analysis_to_json_dict(analysis: DecisionAnalysis) -> dict[str, Any]:
    return {
        "decision_analysis_id": str(analysis.decision_analysis_id),
        "search_profile_id": str(analysis.search_profile_id) if analysis.search_profile_id is not None else None,
        "technical_entity_id": str(analysis.technical_entity_id) if analysis.technical_entity_id is not None else None,
        "local_entity_id": str(analysis.local_entity_id) if analysis.local_entity_id is not None else None,
        "candidate_entity_id": analysis.candidate_entity_id,
        "candidate_name": analysis.candidate_name,
        "candidate_type": analysis.candidate_type,
        "decision": analysis.decision,
        "decision_confidence": analysis.decision_confidence,
        "decision_reason": analysis.decision_reason,
        "manual_review_required": analysis.manual_review_required,
        "affected_claim_ids": list(analysis.affected_claim_ids),
        "evidence": dict(analysis.evidence or {}),
        "builder_version": analysis.builder_version,
        "created_at": analysis.created_at.isoformat(),
    }


__all__ = [
    "DECISION_ENGINE_VERSION",
    "DecisionAnalysis",
    "decision_analysis_to_json_dict",
]
