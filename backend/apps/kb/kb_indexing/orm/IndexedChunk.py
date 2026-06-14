from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class IndexedChunk(TenantSchemaBase):
    __tablename__ = "kb_indexed_chunks"

    id = Column(String(64), primary_key=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    knowledge_base_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    embedding_id = Column(String(64), nullable=False, index=True)
    indexing_job_id = Column(String(64), nullable=False, index=True)

    qdrant_collection = Column(String(128), nullable=False, default="")
    qdrant_point_id = Column(String(128), nullable=False, index=True)

    payload_hash = Column(String(128), nullable=True, index=True)
    vector_hash = Column(String(128), nullable=True, index=True)

    indexed_at = Column(DateTime, nullable=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["IndexedChunk"]
