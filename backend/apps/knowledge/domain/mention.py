from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MentionType(str, Enum):
    PERSON = "person"
    COMPANY = "company"
    SOFTWARE = "software"
    MODULE = "module"
    FEATURE = "feature"
    POLICY = "policy"
    PROCESS = "process"
    LOCATION = "location"
    EVENT = "event"
    OBJECT = "object"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Mention:
    id: str = field(default_factory=lambda: str(uuid4()))
    tenant: str = ""
    corpus_uuid: str = ""
    source_id: str = ""
    document_id: str = ""
    sentence_id: str = ""
    interpretation_run_id: str = ""
    mention_type: str | MentionType = MentionType.UNKNOWN.value
    text_content: str = ""
    normalized_value: str | None = None
    char_start: int = 0
    char_end: int = 0
    confidence: float = 0.5
    created_at: datetime = field(default_factory=_utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.mention_type, MentionType):
            object.__setattr__(self, "mention_type", self.mention_type.value)

    @property
    def mention_id(self) -> str:
        return self.id

    @property
    def surface_text(self) -> str:
        return self.text_content

    @property
    def normalized_text(self) -> str:
        return self.normalized_value or ""

    def debug_repr(self) -> str:
        return f"[MENTION] {self.surface_text} ({self.mention_type}) @ {self.char_start}-{self.char_end} | norm={self.normalized_text}"


__all__ = ["Mention", "MentionType"]
