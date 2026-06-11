from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from apps.kb.kb_ingest.dto.TrainingItemSummaryResponse import TrainingItemSummaryResponse
from apps.kb.kb_ingest.enums.TrainingBatchStatus import TrainingBatchStatus


class TrainingTextResponse(BaseModel):
    """HTTP válasz a szöveges tanítás beküldésére (`TrainingTextRequest` párja)."""

    model_config = ConfigDict(use_enum_values=True)

    batch_id: str
    status: TrainingBatchStatus
    created_at: datetime
    completed_at: datetime | None = None
    batch_size: int = 1
    accepted_count: int = 0
    failed_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    items: list[TrainingItemSummaryResponse] = Field(default_factory=list)


__all__ = ["TrainingTextResponse"]
