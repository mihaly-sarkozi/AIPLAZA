from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class TemporalMention(TenantSchemaBase):
    __tablename__ = "kb_temporal_mentions"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    raw_text = Column(String(256), nullable=False)
    normalized_start = Column(String(64), nullable=True)
    normalized_end = Column(String(64), nullable=True)
    temporal_type = Column(String(32), nullable=False, index=True)
    start_offset = Column(Integer, nullable=True)
    end_offset = Column(Integer, nullable=True)
    language_code = Column(String(8), nullable=True, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    recognizer_name = Column(String(64), nullable=False, default="")
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["TemporalMention"]
