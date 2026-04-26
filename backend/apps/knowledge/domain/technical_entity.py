from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


TECHNICAL_ENTITY_BUILDER_VERSION = "technical_entity_builder_v1"


@dataclass(frozen=True)
class TechnicalEntity:
    """Structured, comparable local technical entity derived from a LocalEntityCluster.

    Scope: local run/source only. This is not a global profile and does not imply similarity/tension behavior.
    """

    technical_entity_id: UUID = field(default_factory=uuid4)
    run_id: UUID | None = None
    source_id: UUID | None = None
    local_entity_id: UUID | None = None

    canonical_name: str = ""
    entity_type: str = "unknown"
    normalized_key: str = ""

    surface_bundle: dict[str, Any] = field(default_factory=dict)
    identity_claims: list[dict[str, Any]] = field(default_factory=list)
    descriptor_claims: list[dict[str, Any]] = field(default_factory=list)
    state_claims: list[dict[str, Any]] = field(default_factory=list)
    relation_claims: list[dict[str, Any]] = field(default_factory=list)
    event_claims: list[dict[str, Any]] = field(default_factory=list)
    rule_claims: list[dict[str, Any]] = field(default_factory=list)
    other_claims: list[dict[str, Any]] = field(default_factory=list)

    time_signature: dict[str, Any] = field(default_factory=dict)
    space_signature: dict[str, Any] = field(default_factory=dict)
    relation_signature: dict[str, Any] = field(default_factory=dict)

    evidence_refs: list[dict[str, Any]] = field(default_factory=list)
    coherence_state: str = "unknown"
    coherence_score: float = 0.0
    confidence: float = 0.0

    builder_version: str = TECHNICAL_ENTITY_BUILDER_VERSION
    created_at: datetime = field(default_factory=_utcnow)


def technical_entity_to_json_dict(entity: TechnicalEntity) -> dict[str, Any]:
    return {
        "technical_entity_id": str(entity.technical_entity_id),
        "run_id": str(entity.run_id) if entity.run_id is not None else None,
        "source_id": str(entity.source_id) if entity.source_id is not None else None,
        "local_entity_id": str(entity.local_entity_id) if entity.local_entity_id is not None else None,
        "canonical_name": entity.canonical_name,
        "entity_type": entity.entity_type,
        "normalized_key": entity.normalized_key,
        "surface_bundle": dict(entity.surface_bundle or {}),
        "identity_claims": list(entity.identity_claims),
        "descriptor_claims": list(entity.descriptor_claims),
        "state_claims": list(entity.state_claims),
        "relation_claims": list(entity.relation_claims),
        "event_claims": list(entity.event_claims),
        "rule_claims": list(entity.rule_claims),
        "other_claims": list(entity.other_claims),
        "time_signature": dict(entity.time_signature or {}),
        "space_signature": dict(entity.space_signature or {}),
        "relation_signature": dict(entity.relation_signature or {}),
        "evidence_refs": list(entity.evidence_refs),
        "coherence_state": entity.coherence_state,
        "coherence_score": entity.coherence_score,
        "confidence": entity.confidence,
        "builder_version": entity.builder_version,
        "created_at": entity.created_at.isoformat(),
    }


__all__ = [
    "TECHNICAL_ENTITY_BUILDER_VERSION",
    "TechnicalEntity",
    "technical_entity_to_json_dict",
]
