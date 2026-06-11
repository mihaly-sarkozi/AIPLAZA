from __future__ import annotations

# backend/apps/kb/kb_understanding/orm/KnowledgeScore.py
# Feladat: Chunk minőségi / rangsorolási alappontszáma (scoring lépés kimenete).
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeScore(TenantSchemaBase):
    __tablename__ = "kb_scores"

    # Egyedi azonosító (score_…).
    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    # Összesített pontszám 0..1 — a keresési ranking alapja.
    knowledge_score = Column(Float, nullable=False, default=0.0, index=True)
    # Komponensenkénti részpontszámok (freshness, structure, source_type, …).
    components = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["KnowledgeScore"]
