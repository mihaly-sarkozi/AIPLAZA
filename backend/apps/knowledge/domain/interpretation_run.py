from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

InterpretationRunStatus = Literal["queued", "processing", "completed", "failed"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class InterpretationRun:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    corpus_uuid: str = ""
    source_id: str = ""
    document_id: str = ""
    status: InterpretationRunStatus = "queued"
    interpreter_type: str = "semantic_interpretation_v1"
    language: str | None = None
    error_message: str | None = None
    created_by: int | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["InterpretationRun", "InterpretationRunStatus"]
