from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from shared.utils.clock import utc_now_naive
from core.kernel.db.model_bases import TenantSchemaBase


class ReadingBatch(TenantSchemaBase):
    __tablename__ = "kb_reading_batches"

    id = Column(String(36), primary_key=True)
    tenant = Column(String(128), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    input_channel = Column(String(32), nullable=False, default="file")
    status = Column(String(32), nullable=False, default="pending", index=True)
    batch_size = Column(Integer, nullable=False, default=0)
    queued_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    rejected_count = Column(Integer, nullable=False, default=0)
    duplicate_count = Column(Integer, nullable=False, default=0)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)


__all__ = ["ReadingBatch"]
