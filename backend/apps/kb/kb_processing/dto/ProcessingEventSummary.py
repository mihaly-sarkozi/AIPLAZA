from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProcessingEventSummary(BaseModel):
    id: str
    tenant_slug: str | None = None
    knowledge_base_id: str
    training_batch_id: str | None = None
    training_item_id: str | None = None
    job_id: str | None = None
    module: str
    stage: str
    step: str
    event_type: str
    status: str
    message: str | None = None
    duration_ms: int | None = None
    input_summary_json: dict = Field(default_factory=dict)
    output_summary_json: dict = Field(default_factory=dict)
    metadata_json: dict = Field(default_factory=dict)
    created_by: int | None = None
    created_at: datetime


__all__ = ["ProcessingEventSummary"]
