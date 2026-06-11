from __future__ import annotations

from pydantic import BaseModel, Field

from apps.kb.kb_ingest.dto.TrainingFileEstimateItemResponse import TrainingFileEstimateItemResponse


class TrainingFileEstimateResponse(BaseModel):
    file_count: int
    total_char_count: int = 0
    total_storage_bytes: int = 0
    can_start: bool = True
    reason: str | None = None
    items: list[TrainingFileEstimateItemResponse] = Field(default_factory=list)


__all__ = ["TrainingFileEstimateResponse"]
