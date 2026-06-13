from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class EntityMention(TenantSchemaBase):
    __tablename__ = "kb_entity_mentions"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    raw_text = Column(String(512), nullable=False)
    normalized_name = Column(String(512), nullable=False, index=True)
    start_offset = Column(Integer, nullable=False, default=0)
    end_offset = Column(Integer, nullable=False, default=0)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["EntityMention"]
