from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeEmbedding(TenantSchemaBase):
    __tablename__ = "kb_embeddings"

    id = Column(String(64), primary_key=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    knowledge_base_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    discovery_job_id = Column(String(64), nullable=False, index=True)
    embedding_job_id = Column(String(64), nullable=False, index=True)

    embedding_provider = Column(String(32), nullable=False, default="")
    embedding_model = Column(String(128), nullable=False, default="")
    embedding_dimension = Column(Integer, nullable=False, default=0)

    embedding_vector = Column(JSONB, nullable=True)
    vector_hash = Column(String(128), nullable=True, index=True)
    content_hash = Column(String(128), nullable=True, index=True)
    embedding_input_hash = Column(String(128), nullable=True, index=True)

    status = Column(String(32), nullable=False, default="COMPLETED", index=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["KnowledgeEmbedding"]
