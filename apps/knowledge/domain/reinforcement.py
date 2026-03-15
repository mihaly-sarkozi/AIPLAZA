from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel

ReinforcementEventType = Literal[
    "EXPLICIT_TRAINING",
    "SOURCE_CONFIRMATION",
    "CHAT_RETRIEVAL_HIT",
    "USER_FOLLOWUP",
    "USER_CONFIRMATION",
    "INDIRECT_ACTIVATION",
]


class ReinforcementEvent(BaseModel):
    id: int | None = None
    kb_id: int
    target_type: str
    target_id: int
    event_type: ReinforcementEventType | str
    weight: float = 1.0
    created_at: datetime | None = None
