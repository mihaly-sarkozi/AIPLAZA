from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class TemporalMention(TenantSchemaBase):
    __tablename__ = "kb_temporal_mentions"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    raw_text = Column(String(256), nullable=False)
    normalized_start = Column(String(64), nullable=True)
    normalized_end = Column(String(64), nullable=True)
    temporal_type = Column(String(32), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["TemporalMention"]
