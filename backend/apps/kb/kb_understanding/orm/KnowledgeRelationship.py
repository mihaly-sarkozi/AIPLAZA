from __future__ import annotations

# backend/apps/kb/kb_understanding/orm/KnowledgeRelationship.py
# Feladat: Kapcsolat entitások, chunkok és dokumentumok között (relationship build kimenete).
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Column, DateTime, Float, String

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeRelationship(TenantSchemaBase):
    __tablename__ = "kb_relationships"

    # Egyedi kapcsolat azonosító (rel_…).
    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    # Forrás oldal: entity | chunk | document | topic.
    from_type = Column(String(32), nullable=False, index=True)
    from_id = Column(String(512), nullable=False, index=True)
    # Cél oldal.
    to_type = Column(String(32), nullable=False, index=True)
    to_id = Column(String(512), nullable=False, index=True)
    # Kapcsolat jellege (pl. mentioned_in, related_to, has_topic).
    relation = Column(String(64), nullable=False, index=True)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["KnowledgeRelationship"]
