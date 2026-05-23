from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

IngestInputType = Literal["text", "file", "url"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class IngestInput:
    id: str = field(default_factory=lambda: str(uuid4()))
    ingest_item_id: str = ""
    tenant: str = ""
    input_type: IngestInputType = "text"
    storage_provider: str | None = None
    bucket_name: str | None = None
    object_key: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    text_content: str | None = None
    origin_url: str | None = None
    external_ref: str | None = None
    checksum_sha256: str | None = None
    encoding: str | None = None
    language_hint: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["IngestInput", "IngestInputType"]
