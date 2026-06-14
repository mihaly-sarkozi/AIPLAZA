from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class IngestItemResponse(BaseModel):
    id: str
    ingest_run_id: str
    corpus_uuid: str
    queue_order: int = 0
    input_type: str
    display_name: str
    title: str
    status: str
    error_code: str | None = None
    error_message: str | None = None
    duplicate_of_item_id: str | None = None
    pipeline_route: str = "default"
    content_hash: str | None = None
    created_at: datetime
    updated_at: datetime
    metadata: dict = Field(default_factory=dict)


class IngestRunResponse(BaseModel):
    id: str
    corpus_uuid: str
    input_channel: str
    status: str
    batch_size: int = 0
    queued_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    duplicate_count: int = 0
    rejected_count: int = 0
    continue_on_error: bool = False
    pipeline_route: str = "default"
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime
    created_by: int | None = None
    metadata: dict = Field(default_factory=dict)
    items: list[IngestItemResponse] = Field(default_factory=list)
    events: list[dict] = Field(default_factory=list)


class IngestRunListSummaryResponse(BaseModel):
    total_run_count: int = 0
    total_item_count: int = 0
    total_char_count: int = 0
    total_sentence_count: int = 0


class IngestRunListResponse(BaseModel):
    items: list[IngestRunResponse]
    total_count: int
    limit: int
    offset: int
    has_more: bool
    summary: IngestRunListSummaryResponse


__all__ = [
    "IngestItemResponse",
    "IngestRunListResponse",
    "IngestRunListSummaryResponse",
    "IngestRunResponse",
]
