from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

SourceType = Literal["text", "file", "url"]
SourceStatus = Literal["pending", "attached", "ingested", "failed"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Source:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    corpus_uuid: str = ""
    title: str = ""
    source_type: SourceType = "text"
    raw_content: str | None = None
    file_ref: str | None = None
    status: SourceStatus = "pending"
    created_by: int | None = None
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["Source", "SourceStatus", "SourceType"]
