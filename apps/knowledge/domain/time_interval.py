from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class TimeInterval(BaseModel):
    id: int | None = None
    kb_id: int
    source_point_id: str
    normalized_text: str
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    granularity: str = "unknown"
    confidence: float = 0.0
