from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProcessingMetricsResponse(BaseModel):
    id: str
    tenant_slug: str | None = None
    knowledge_base_id: str
    documents_total: int = 0
    documents_ingested: int = 0
    documents_understanding_ready: int = 0
    documents_discovery_ready: int = 0
    documents_indexed: int = 0
    documents_failed: int = 0
    documents_partial: int = 0
    batches_total: int = 0
    items_total: int = 0
    extracted_parts_total: int = 0
    normalized_parts_total: int = 0
    chunks_total: int = 0
    issues_open: int = 0
    issues_warning: int = 0
    issues_error: int = 0
    issues_critical: int = 0
    last_ingested_at: datetime | None = None
    last_processed_at: datetime | None = None
    last_failed_at: datetime | None = None
    last_indexed_at: datetime | None = None
    metadata_json: dict = Field(default_factory=dict)
    updated_at: datetime


__all__ = ["ProcessingMetricsResponse"]
