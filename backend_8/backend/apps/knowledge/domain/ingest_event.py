from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class IngestEvent:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    ingest_run_id: str = ""
    ingest_item_id: str | None = None
    event_type: str = ""
    status: str = "info"
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)
    created_by: int | None = None


__all__ = ["IngestEvent"]
