from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from apps.kb.kb_ingest.enums.TrainingErrorCode import TrainingErrorCode
from apps.kb.kb_ingest.enums.TrainingItemStatus import TrainingItemStatus


class TrainingItemSummaryResponse(BaseModel):
    """Item összefoglaló poll / submit válaszhoz — nincs raw_ref, audit, retry mező."""

    model_config = ConfigDict(use_enum_values=True)

    id: str
    input_type: str
    title: str
    status: TrainingItemStatus
    error_code: TrainingErrorCode | None = None
    error_message: str | None = None
    char_count: int | None = None


__all__ = ["TrainingItemSummaryResponse"]
