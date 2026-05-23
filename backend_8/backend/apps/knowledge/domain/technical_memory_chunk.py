from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


TECHNICAL_MEMORY_CHUNK_BUILDER_VERSION = "technical_memory_chunk_builder_v1"


@dataclass(frozen=True)
class TechnicalMemoryChunk:
    """Local, rebuildable working-memory chunk derived from a TechnicalEntity.

    Scope: run/source local only. This is not a global profile, vector index, or retrieval chunk.
    """

    technical_memory_chunk_id: UUID = field(default_factory=uuid4)
    run_id: UUID | None = None
    source_id: UUID | None = None
    technical_entity_id: UUID | None = None
    local_entity_id: UUID | None = None

    entity_name: str = ""
    entity_type: str = "unknown"
    normalized_key: str = ""

    summary_text: str = ""

    facts: list[dict[str, Any]] = field(default_factory=list)
    time_profile: dict[str, Any] = field(default_factory=dict)
    space_profile: dict[str, Any] = field(default_factory=dict)
    relation_profile: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = field(default_factory=list)

    coherence_state: str = "unknown"
    coherence_score: float = 0.0
    confidence: float = 0.0

    builder_version: str = TECHNICAL_MEMORY_CHUNK_BUILDER_VERSION
    created_at: datetime = field(default_factory=_utcnow)


def technical_memory_chunk_to_json_dict(chunk: TechnicalMemoryChunk) -> dict[str, Any]:
    return {
        "technical_memory_chunk_id": str(chunk.technical_memory_chunk_id),
        "run_id": str(chunk.run_id) if chunk.run_id is not None else None,
        "source_id": str(chunk.source_id) if chunk.source_id is not None else None,
        "technical_entity_id": str(chunk.technical_entity_id) if chunk.technical_entity_id is not None else None,
        "local_entity_id": str(chunk.local_entity_id) if chunk.local_entity_id is not None else None,
        "entity_name": chunk.entity_name,
        "entity_type": chunk.entity_type,
        "normalized_key": chunk.normalized_key,
        "summary_text": chunk.summary_text,
        "facts": list(chunk.facts),
        "time_profile": dict(chunk.time_profile or {}),
        "space_profile": dict(chunk.space_profile or {}),
        "relation_profile": dict(chunk.relation_profile or {}),
        "evidence_refs": list(chunk.evidence_refs),
        "coherence_state": chunk.coherence_state,
        "coherence_score": chunk.coherence_score,
        "confidence": chunk.confidence,
        "builder_version": chunk.builder_version,
        "created_at": chunk.created_at.isoformat(),
    }


__all__ = [
    "TECHNICAL_MEMORY_CHUNK_BUILDER_VERSION",
    "TechnicalMemoryChunk",
    "technical_memory_chunk_to_json_dict",
]
