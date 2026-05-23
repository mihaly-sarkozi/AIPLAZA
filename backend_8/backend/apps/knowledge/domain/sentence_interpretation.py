from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SentenceInterpretation:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    corpus_uuid: str = ""
    source_id: str = ""
    document_id: str = ""
    sentence_id: str = ""
    interpretation_run_id: str = ""
    sentence_text: str = ""
    claim_summary: str = ""
    assertion_mode: str = "fact"
    claim_type: str = "other"
    time_mode: str = "unknown"
    time_label: str | None = None
    space_mode: str = "unknown"
    space_label: str | None = None
    confidence: float = 0.0
    information_value_score: float = 0.0
    information_value_status: str = "unrated"
    information_value_reason: str | None = None
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["SentenceInterpretation"]
