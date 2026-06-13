from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeTopic(TenantSchemaBase):
    __tablename__ = "kb_topics"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    topic_key = Column(String(128), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["KnowledgeTopic"]
