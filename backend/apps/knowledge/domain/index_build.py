from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

IndexBuildStatus = Literal["pending", "building", "ready", "failed"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class IndexBuild:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    corpus_uuid: str = ""
    index_profile_key: str = "basic_chunk_v1"
    status: IndexBuildStatus = "pending"
    collection_name: str = ""
    chunk_count: int = 0
    error: str | None = None
    created_by: int | None = None
    created_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["IndexBuild", "IndexBuildStatus"]
