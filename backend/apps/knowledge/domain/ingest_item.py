from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

IngestItemType = Literal["text", "file", "url"]
IngestItemStatus = Literal[
    "received",
    "validated",
    "queued",
    "processing",
    "completed",
    "duplicate",
    "rejected",
    "failed",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class IngestItem:
    id: str = field(default_factory=lambda: str(uuid4()))
    ingest_run_id: str = ""
    tenant: str = ""
    corpus_uuid: str = ""
    queue_order: int = 0
    input_type: IngestItemType = "text"
    display_name: str = ""
    title: str = ""
    origin: str | None = None
    status: IngestItemStatus = "received"
    progress_message: str | None = None
    result_message: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    duplicate_of_item_id: str | None = None
    duplicate_of_source_id: str | None = None
    pipeline_route: str = "source_parser"
    parser_job_id: str | None = None
    source_id: str | None = None
    content_hash: str | None = None
    created_by: int | None = None
    created_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["IngestItem", "IngestItemStatus", "IngestItemType"]
