from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeEntity(TenantSchemaBase):
    __tablename__ = "kb_entities"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    document_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    name = Column(String(512), nullable=False)
    normalized_name = Column(String(512), nullable=False, index=True)
    aliases = Column(JSONB, nullable=False, default=list)
    confidence = Column(Float, nullable=False, default=0.0)
    chunk_ids = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["KnowledgeEntity"]
