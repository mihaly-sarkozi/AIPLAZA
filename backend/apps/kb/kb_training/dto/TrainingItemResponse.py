from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from apps.kb.kb_training.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_training.enums.TrainingItemStatus import TrainingItemStatus


class TrainingItemResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: str
    training_batch_id: str
    knowledge_base_id: str
    input_type: str
    title: str
    status: TrainingItemStatus
    raw_ref: str | None = None
    content_hash: str | None = None
    error_code: TrainingErrorCode | None = None
    error_message: str | None = None
    retryable: bool = False
    retry_count: int = 0
    duplicate_of_item_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = ["TrainingItemResponse"]
