from __future__ import annotations

# backend/apps/kb/kb_understanding/orm/KnowledgeEntity.py
# Feladat: Chunkokból kinyert entitás (entity extraction kimenete).
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Column, DateTime, Float, String
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeEntity(TenantSchemaBase):
    __tablename__ = "kb_entities"

    # Egyedi entitás azonosító (entity_…).
    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    document_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    # EntityType érték.
    entity_type = Column(String(32), nullable=False, index=True)
    # Ahogy a szövegben szerepelt.
    name = Column(String(512), nullable=False)
    # Normalizált (kisbetűs, trimmelt) név — alias-egyesítéshez.
    normalized_name = Column(String(512), nullable=False, index=True)
    # Alternatív megnevezések listája.
    aliases = Column(JSONB, nullable=False, default=list)
    # Felismerési bizonyosság 0..1.
    confidence = Column(Float, nullable=False, default=0.0)
    # Chunk azonosítók, amelyekben az entitás előfordul.
    chunk_ids = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["KnowledgeEntity"]
