from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Sentence:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    corpus_uuid: str = ""
    source_id: str = ""
    document_id: str = ""
    paragraph_id: str = ""
    order_index: int = 0
    text_content: str = ""
    char_start: int = 0
    char_end: int = 0
    token_count: int = 0
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["Sentence"]
