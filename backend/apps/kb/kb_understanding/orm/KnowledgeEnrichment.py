from __future__ import annotations

# backend/apps/kb/kb_understanding/orm/KnowledgeEnrichment.py
# Feladat: Chunkhoz tartozó AI-többletmetaadat (enrichment lépés kimenete).
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeEnrichment(TenantSchemaBase):
    __tablename__ = "kb_enrichments"

    # Egyedi azonosító (enrich_…).
    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    # Rövid összefoglaló.
    summary = Column(Text, nullable=False, default="")
    keywords = Column(JSONB, nullable=False, default=list)
    topics = Column(JSONB, nullable=False, default=list)
    # Kérdések, amikre a chunk válaszolhat.
    possible_questions = Column(JSONB, nullable=False, default=list)
    # Tartalomtípus (pl. process, faq, policy, reference).
    content_type = Column(String(64), nullable=True)
    # Nyelv (ISO 639-1).
    language = Column(String(8), nullable=True)
    # Nehézségi szint (pl. basic | intermediate | advanced).
    difficulty = Column(String(32), nullable=True)
    # Fontosság 0..1.
    importance = Column(Float, nullable=False, default=0.0)
    # Az enrichment bizonyossága 0..1.
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["KnowledgeEnrichment"]
