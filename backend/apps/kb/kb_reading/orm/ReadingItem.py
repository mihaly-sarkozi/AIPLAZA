from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from shared.utils.clock import utc_now_naive
from core.kernel.db.model_bases import TenantSchemaBase


class ReadingItem(TenantSchemaBase):
    __tablename__ = "kb_reading_items"

    id = Column(String(36), primary_key=True)
    reading_batch_id = Column(String(36), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    input_type = Column(String(16), nullable=False, index=True)
    title = Column(String(200), nullable=False, default="")
    status = Column(String(32), nullable=False, default="pending", index=True)
    raw_ref = Column(String(1024), nullable=True)
    content_hash = Column(String(128), nullable=True, index=True)
    idempotency_key = Column(String(192), nullable=True, index=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    retryable = Column(Boolean, nullable=False, default=False)
    retry_count = Column(Integer, nullable=False, default=0)
    duplicate_of_item_id = Column(String(36), nullable=True)
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(255), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    origin_url = Column(String(2048), nullable=True, index=True)
    final_url = Column(String(2048), nullable=True)
    status_code = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)


__all__ = ["ReadingItem"]
