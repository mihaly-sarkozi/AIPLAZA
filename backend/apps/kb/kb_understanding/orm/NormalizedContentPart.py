from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class NormalizedContentPart(TenantSchemaBase):
    __tablename__ = "kb_normalized_content_parts"

    id = Column(String(64), primary_key=True)
    normalized_content_id = Column(String(64), nullable=False, index=True)
    source_part_id = Column(String(64), nullable=True, index=True)

    job_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)

    part_type = Column(String(32), nullable=False, index=True)
    normalized_text = Column(Text, nullable=False, default="")

    page_number = Column(Integer, nullable=True, index=True)
    part_index = Column(Integer, nullable=False, default=0)
    document_order = Column(Integer, nullable=True, index=True)

    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)

    status = Column(String(32), nullable=False, default="completed")
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["NormalizedContentPart"]
