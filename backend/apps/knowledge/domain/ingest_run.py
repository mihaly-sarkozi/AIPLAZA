from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

IngestRunStatus = Literal["received", "queued", "processing", "partial_success", "completed", "failed"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class IngestRun:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    corpus_uuid: str = ""
    input_channel: str = "manual"
    status: IngestRunStatus = "received"
    batch_size: int = 0
    queued_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    continue_on_error: bool = True
    pipeline_route: str = "source_parser"
    created_by: int | None = None
    created_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["IngestRun", "IngestRunStatus"]
