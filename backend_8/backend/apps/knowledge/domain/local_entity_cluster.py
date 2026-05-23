from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LocalEntityType(str, Enum):
    PERSON = "person"
    COMPANY = "company"
    SOFTWARE = "software"
    MODULE = "module"
    SYSTEM = "system"
    FEATURE = "feature"
    POLICY = "policy"
    PROCESS = "process"
    LOCATION = "location"
    ACCOUNT = "account"
    USER = "user"
    CHECKLIST = "checklist"
    DOCUMENT = "document"
    OBJECT = "object"
    UNKNOWN = "unknown"


def local_entity_type_values() -> frozenset[str]:
    return frozenset(item.value for item in LocalEntityType)


@dataclass(frozen=True)
class LocalEntityCluster:
    local_entity_id: UUID = field(default_factory=uuid4)
    run_id: UUID | None = None
    source_id: UUID | None = None
    canonical_name: str = ""
    entity_type: str = LocalEntityType.UNKNOWN.value
    normalized_key: str = ""
    mention_ids: list[UUID] = field(default_factory=list)
    claim_ids: list[UUID] = field(default_factory=list)
    sentence_ids: list[UUID] = field(default_factory=list)
    surface_forms: list[str] = field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    coherence_score: float = 0.0
    resolver_version: str = "local_resolver_v1"
    created_at: datetime = field(default_factory=_utcnow)
    explanation: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.entity_type, LocalEntityType):
            object.__setattr__(self, "entity_type", self.entity_type.value)
        allowed = local_entity_type_values()
        if self.entity_type not in allowed:
            object.__setattr__(self, "entity_type", LocalEntityType.UNKNOWN.value)
        if not isinstance(self.explanation, dict):
            object.__setattr__(self, "explanation", {})

    def debug_repr(self) -> str:
        return (
            "[LOCAL ENTITY]\n"
            f"name={self.canonical_name}\n"
            f"type={self.entity_type}\n"
            f"claims={len(self.claim_ids)}\n"
            f"mentions={len(self.mention_ids)}\n"
            f"coherence={self.coherence_score:.4f}\n"
            f"key={self.normalized_key}"
        )


def local_entity_cluster_to_json_dict(cluster: LocalEntityCluster) -> dict[str, Any]:
    explanation = dict(cluster.explanation or {})
    canonical_key = str(explanation.get("canonical_key") or cluster.normalized_key or "")
    alias_match_reason = explanation.get("alias_match_reason")
    return {
        "local_entity_id": str(cluster.local_entity_id),
        "run_id": str(cluster.run_id) if cluster.run_id is not None else None,
        "source_id": str(cluster.source_id) if cluster.source_id is not None else None,
        "canonical_name": cluster.canonical_name,
        "canonical_key": canonical_key,
        "entity_type": cluster.entity_type,
        "normalized_key": cluster.normalized_key,
        "mention_ids": [str(item) for item in cluster.mention_ids],
        "claim_ids": [str(item) for item in cluster.claim_ids],
        "sentence_ids": [str(item) for item in cluster.sentence_ids],
        "surface_forms": list(cluster.surface_forms),
        "evidence_refs": list(cluster.evidence_refs),
        "confidence": cluster.confidence,
        "coherence_score": cluster.coherence_score,
        "resolver_version": cluster.resolver_version,
        "created_at": cluster.created_at.isoformat(),
        "alias_match_reason": alias_match_reason,
        "explanation": explanation,
    }


__all__ = [
    "LocalEntityCluster",
    "LocalEntityType",
    "local_entity_cluster_to_json_dict",
    "local_entity_type_values",
]
