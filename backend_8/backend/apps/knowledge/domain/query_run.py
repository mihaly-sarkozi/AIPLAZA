from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Citation:
    source_id: str
    build_id: str
    snippet: str
    score: float
    title: str | None = None
    chunk_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QueryRun:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    query: str = ""
    corpus_uuid: str = ""
    build_ids: list[str] = field(default_factory=list)
    retrieval_profile_key: str = "basic_retrieval_v1"
    context_profile_key: str = "chat_context_v1"
    latency_ms: float = 0.0
    result_count: int = 0
    citations: list[Citation] = field(default_factory=list)
    context_text: str = ""
    feedback: str | None = None
    compare_mode: bool = False
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["Citation", "QueryRun"]
