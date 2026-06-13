from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class ProcessingEvent(TenantSchemaBase):
    __tablename__ = "kb_processing_events"

    id = Column(String(64), primary_key=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    training_batch_id = Column(String(64), nullable=True, index=True)
    training_item_id = Column(String(64), nullable=True, index=True)
    job_id = Column(String(64), nullable=True, index=True)
    module = Column(String(64), nullable=False, index=True)
    stage = Column(String(64), nullable=False, index=True)
    step = Column(String(64), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, index=True)
    message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    input_summary_json = Column(JSONB, nullable=False, default=dict)
    output_summary_json = Column(JSONB, nullable=False, default=dict)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)


__all__ = ["ProcessingEvent"]
