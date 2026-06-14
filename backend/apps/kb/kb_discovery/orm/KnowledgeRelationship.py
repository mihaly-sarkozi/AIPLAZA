from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeRelationship(TenantSchemaBase):
    __tablename__ = "kb_relationships"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    from_type = Column(String(32), nullable=False, index=True)
    from_id = Column(String(512), nullable=False, index=True)
    to_type = Column(String(32), nullable=False, index=True)
    to_id = Column(String(512), nullable=False, index=True)
    relation = Column(String(64), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    weight = Column(Float, nullable=False, default=0.0)
    evidence_chunk_ids = Column(JSONB, nullable=False, default=list)
    evidence_text = Column(Text, nullable=False, default="")
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["KnowledgeRelationship"]
