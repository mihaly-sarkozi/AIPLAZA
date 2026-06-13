from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class ExtractedContent(TenantSchemaBase):
    __tablename__ = "kb_extracted_content"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)

    raw_ref = Column(String(1024), nullable=True)
    mime_type = Column(String(255), nullable=True)

    extractor_name = Column(String(64), nullable=False, default="")
    extractor_version = Column(String(32), nullable=False, default="1.0")

    total_pages = Column(Integer, nullable=True)
    total_chars = Column(Integer, nullable=False, default=0)

    text_parts_count = Column(Integer, nullable=False, default=0)
    table_parts_count = Column(Integer, nullable=False, default=0)
    ocr_text_parts_count = Column(Integer, nullable=False, default=0)
    ocr_empty_parts_count = Column(Integer, nullable=False, default=0)
    ocr_failed_parts_count = Column(Integer, nullable=False, default=0)

    status = Column(String(32), nullable=False, default="completed", index=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["ExtractedContent"]
