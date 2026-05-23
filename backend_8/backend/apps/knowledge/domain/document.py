from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

DocumentStatus = Literal["draft", "ready", "failed"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Document:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    corpus_uuid: str = ""
    source_id: str = ""
    parser_run_id: str = ""
    title: str = ""
    language: str | None = None
    text_content: str = ""
    char_count: int = 0
    status: DocumentStatus = "draft"
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["Document", "DocumentStatus"]
