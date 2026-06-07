from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TrainingEventResponse(BaseModel):
    id: str
    training_batch_id: str
    training_item_id: str | None = None
    event_type: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


__all__ = ["TrainingEventResponse"]
