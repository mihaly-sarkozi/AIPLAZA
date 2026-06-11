from __future__ import annotations

from pydantic import BaseModel, Field

from apps.kb.kb_ingest.dto.TrainingBatchSummaryResponse import TrainingBatchSummaryResponse
from apps.kb.kb_ingest.dto.TrainingItemSummaryResponse import TrainingItemSummaryResponse


class TrainingBatchStatusResponse(BaseModel):
    """Batch poll válasz — batch összegzés + item lista, audit események nélkül."""

    batch: TrainingBatchSummaryResponse
    items: list[TrainingItemSummaryResponse] = Field(default_factory=list)


__all__ = ["TrainingBatchStatusResponse"]
