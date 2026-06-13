from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeRelationship(TenantSchemaBase):
    __tablename__ = "kb_relationships"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    from_type = Column(String(32), nullable=False, index=True)
    from_id = Column(String(512), nullable=False, index=True)
    to_type = Column(String(32), nullable=False, index=True)
    to_id = Column(String(512), nullable=False, index=True)
    relation = Column(String(64), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["KnowledgeRelationship"]
