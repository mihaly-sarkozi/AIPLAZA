from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apps.kb.kb_training.enums.TrainingBatchStatus import TrainingBatchStatus


class TrainingBatchResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    tenant: str
    knowledge_base_id: str
    input_channel: str
    status: TrainingBatchStatus
    batch_size: int
    queued_count: int
    failed_count: int
    rejected_count: int
    duplicate_count: int
    created_by: int
    created_at: datetime
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = ["TrainingBatchResponse"]
