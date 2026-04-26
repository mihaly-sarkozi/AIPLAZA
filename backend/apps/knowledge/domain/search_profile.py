from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


SEARCH_PROFILE_BUILDER_VERSION = "search_profile_builder_v1"


@dataclass(frozen=True)
class SearchProfile:
    """Structured local search profile derived from a TechnicalMemoryChunk.

    Scope: local run/source only. This is not candidate selection, a similarity engine, or Qdrant indexing.
    """

    search_profile_id: UUID = field(default_factory=uuid4)
    run_id: UUID | None = None
    source_id: UUID | None = None
    technical_memory_chunk_id: UUID | None = None
    technical_entity_id: UUID | None = None
    local_entity_id: UUID | None = None

    entity_name: str = ""
    entity_type: str = "unknown"
    normalized_key: str = ""

    canonical_text: str = ""
    search_text: str = ""
    aliases: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    claim_group_signals: dict[str, Any] = field(default_factory=dict)
    time_filters: dict[str, Any] = field(default_factory=dict)
    space_filters: dict[str, Any] = field(default_factory=dict)
    relation_filters: dict[str, Any] = field(default_factory=dict)

    evidence_refs: list[dict[str, Any]] = field(default_factory=list)

    builder_version: str = SEARCH_PROFILE_BUILDER_VERSION
    created_at: datetime = field(default_factory=_utcnow)


def search_profile_to_json_dict(profile: SearchProfile) -> dict[str, Any]:
    return {
        "search_profile_id": str(profile.search_profile_id),
        "run_id": str(profile.run_id) if profile.run_id is not None else None,
        "source_id": str(profile.source_id) if profile.source_id is not None else None,
        "technical_memory_chunk_id": (
            str(profile.technical_memory_chunk_id) if profile.technical_memory_chunk_id is not None else None
        ),
        "technical_entity_id": str(profile.technical_entity_id) if profile.technical_entity_id is not None else None,
        "local_entity_id": str(profile.local_entity_id) if profile.local_entity_id is not None else None,
        "entity_name": profile.entity_name,
        "entity_type": profile.entity_type,
        "normalized_key": profile.normalized_key,
        "canonical_text": profile.canonical_text,
        "search_text": profile.search_text,
        "aliases": list(profile.aliases),
        "keywords": list(profile.keywords),
        "claim_group_signals": dict(profile.claim_group_signals or {}),
        "time_filters": dict(profile.time_filters or {}),
        "space_filters": dict(profile.space_filters or {}),
        "relation_filters": dict(profile.relation_filters or {}),
        "evidence_refs": list(profile.evidence_refs),
        "builder_version": profile.builder_version,
        "created_at": profile.created_at.isoformat(),
    }


__all__ = [
    "SEARCH_PROFILE_BUILDER_VERSION",
    "SearchProfile",
    "search_profile_to_json_dict",
]
