from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeKeyword(TenantSchemaBase):
    __tablename__ = "kb_keywords"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    term = Column(String(256), nullable=False, index=True)
    normalized_term = Column(String(256), nullable=False, index=True)
    display_term = Column(String(256), nullable=False, default="")
    language_code = Column(String(8), nullable=True, index=True)
    rank = Column(Integer, nullable=False, default=0)
    score = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.0)
    source = Column(String(64), nullable=False, default="")
    extractor_version = Column(String(32), nullable=False, default="")
    start_offset = Column(Integer, nullable=True)
    end_offset = Column(Integer, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["KnowledgeKeyword"]
