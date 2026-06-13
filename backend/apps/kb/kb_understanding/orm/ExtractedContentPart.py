from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class ExtractedContentPart(TenantSchemaBase):
    __tablename__ = "kb_extracted_content_parts"

    id = Column(String(64), primary_key=True)
    extracted_content_id = Column(String(64), nullable=False, index=True)
    job_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)

    part_type = Column(String(32), nullable=False, index=True)
    page_number = Column(Integer, nullable=True, index=True)
    part_index = Column(Integer, nullable=False, default=0)

    text = Column(Text, nullable=True)
    raw_payload_json = Column("raw_payload", JSONB, nullable=False, default=dict)
    char_count = Column(Integer, nullable=False, default=0)

    status = Column(String(32), nullable=False, default="completed")
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)


__all__ = ["ExtractedContentPart"]
