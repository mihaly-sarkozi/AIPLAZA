from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimeMode(str, Enum):
    BOUNDED = "bounded"
    OPEN = "open"
    CURRENT = "current"
    EVENT = "event"
    ZERO_TIME = "zero_time"
    UNKNOWN = "unknown"


class SpaceMode(str, Enum):
    BOUNDED = "bounded"
    IRRELEVANT = "irrelevant"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SpaceTimeFrame:
    id: str = field(default_factory=lambda: str(uuid4()))
    claim_id: str | None = None
    sentence_id: str | None = None
    source_id: str | None = None
    language: str = "unknown"
    time_mode: str | TimeMode = TimeMode.UNKNOWN.value
    time_value: str | None = None
    time_start: datetime | None = None
    time_end: datetime | None = None
    time_precision: str | None = None
    time_confidence: float = 0.5
    space_mode: str | SpaceMode = SpaceMode.UNKNOWN.value
    space_value: str | None = None
    space_precision: str | None = None
    space_confidence: float = 0.5
    overall_confidence: float = 0.5
    created_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        if isinstance(self.time_mode, TimeMode):
            object.__setattr__(self, "time_mode", self.time_mode.value)
        if isinstance(self.space_mode, SpaceMode):
            object.__setattr__(self, "space_mode", self.space_mode.value)

    @property
    def frame_id(self) -> str:
        return self.id

    def debug_repr(self) -> str:
        return (
            f"[SPACE-TIME] time={self.time_mode}:{self.time_value} "
            f"space={self.space_mode}:{self.space_value} conf={self.overall_confidence}"
        )


__all__ = ["SpaceMode", "SpaceTimeFrame", "TimeMode"]
