from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeEnrichment(TenantSchemaBase):
    __tablename__ = "kb_enrichments"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    lead_sentence = Column(Text, nullable=False, default="")
    keywords = Column(JSONB, nullable=False, default=list)
    topics = Column(JSONB, nullable=False, default=list)
    content_type = Column(String(64), nullable=True)
    language_code = Column(String(8), nullable=True, index=True)
    language_confidence = Column(Float, nullable=False, default=0.0)
    possible_questions = Column(JSONB, nullable=False, default=list)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["KnowledgeEnrichment"]
