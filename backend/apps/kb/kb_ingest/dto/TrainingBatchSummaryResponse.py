from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from apps.kb.kb_ingest.enums.TrainingBatchStatus import TrainingBatchStatus


class TrainingBatchSummaryResponse(BaseModel):
    """Batch állapot pollhoz — csak a UI / progress számításhoz kellő mezők."""

    model_config = ConfigDict(use_enum_values=True)

    id: str
    knowledge_base_id: str
    input_channel: str
    status: TrainingBatchStatus
    batch_size: int
    accepted_count: int
    failed_count: int
    duplicate_count: int
    rejected_count: int
    created_at: datetime
    completed_at: datetime | None = None
    progress: dict[str, Any] | None = None


__all__ = ["TrainingBatchSummaryResponse"]
