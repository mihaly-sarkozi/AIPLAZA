from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class NormalizedContent(TenantSchemaBase):
    __tablename__ = "kb_normalized_content"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)

    status = Column(String(32), nullable=False, default="processing")
    part_count = Column(Integer, nullable=False, default=0)
    total_chars = Column(Integer, nullable=False, default=0)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)

    # Legacy columns — not written by the part-based normalize flow.
    text = Column(Text, nullable=False, default="")
    page_map = Column(JSONB, nullable=False, default=list)
    part_map = Column(JSONB, nullable=False, default=list)
    char_count = Column(Integer, nullable=False, default=0)
    applied_rules = Column(JSONB, nullable=False, default=dict)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["NormalizedContent"]
