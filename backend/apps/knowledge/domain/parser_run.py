from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

ParserRunStatus = Literal["queued", "processing", "completed", "failed"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ParserRun:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    corpus_uuid: str = ""
    source_id: str = ""
    status: ParserRunStatus = "queued"
    parser_type: str = "basic_text_v1"
    language: str | None = None
    error_message: str | None = None
    created_by: int | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["ParserRun", "ParserRunStatus"]
