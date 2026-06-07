from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from apps.kb.kb_training.dto.TrainingItemSummaryResponse import TrainingItemSummaryResponse
from apps.kb.kb_training.enums.TrainingBatchStatus import TrainingBatchStatus


class TrainingSubmitResponse(BaseModel):
    """Beküldés válasz — alapból csak azonosító + állapot; több itemnél opcionális részletek."""

    model_config = ConfigDict(use_enum_values=True)

    batch_id: str
    status: TrainingBatchStatus
    batch_size: int = 1
    accepted_count: int = 0
    failed_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    items: list[TrainingItemSummaryResponse] = Field(default_factory=list)


__all__ = ["TrainingSubmitResponse"]
