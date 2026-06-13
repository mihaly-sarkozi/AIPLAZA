from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProcessingIssueSummary(BaseModel):
    id: str
    tenant_slug: str | None = None
    knowledge_base_id: str
    training_batch_id: str | None = None
    training_item_id: str | None = None
    job_id: str | None = None
    module: str
    stage: str
    step: str | None = None
    severity: str
    issue_code: str
    issue_message: str | None = None
    status: str
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None
    occurrence_count: int
    metadata_json: dict = Field(default_factory=dict)


__all__ = ["ProcessingIssueSummary"]
