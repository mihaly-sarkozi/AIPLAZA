from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeEnrichment(TenantSchemaBase):
    __tablename__ = "kb_enrichments"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    language_code = Column(String(8), nullable=True, index=True)
    language_confidence = Column(Float, nullable=False, default=0.0)
    lead_sentence = Column(Text, nullable=False, default="")
    preview_text = Column(Text, nullable=False, default="")
    content_type = Column(String(64), nullable=True)
    content_type_confidence = Column(Float, nullable=False, default=0.0)
    profile_confidence = Column(Float, nullable=False, default=0.0)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["KnowledgeEnrichment"]
