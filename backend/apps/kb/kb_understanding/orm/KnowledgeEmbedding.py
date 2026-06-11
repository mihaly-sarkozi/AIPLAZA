from __future__ import annotations

# backend/apps/kb/kb_understanding/orm/KnowledgeEmbedding.py
# Feladat: Chunkhoz tartozó embedding vektor és modell-metaadat (embedding lépés kimenete).
# A vektor JSONB-ben tárolódik; a kereső indexbe írás a kb_indexing dolga.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeEmbedding(TenantSchemaBase):
    __tablename__ = "kb_embeddings"

    # Egyedi azonosító (emb_…).
    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    # Mit embeddingeltünk: chunk_text | summary.
    target = Column(String(16), nullable=False, default="chunk_text", index=True)
    # A vektor (float lista) — kb_indexing olvassa.
    vector = Column(JSONB, nullable=False, default=list)
    embedding_model = Column(String(255), nullable=False)
    embedding_dimension = Column(Integer, nullable=False, default=0)
    embedding_created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["KnowledgeEmbedding"]
