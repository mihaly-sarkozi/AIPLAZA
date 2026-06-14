from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class IndexVerificationItem(TenantSchemaBase):
    __tablename__ = "kb_index_verification_items"

    id = Column(String(64), primary_key=True)
    verification_id = Column(String(64), nullable=False, index=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    knowledge_base_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    indexing_job_id = Column(String(64), nullable=False, index=True)
    indexed_chunk_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    embedding_id = Column(String(64), nullable=False, index=True)

    qdrant_collection = Column(String(128), nullable=False, default="")
    qdrant_point_id = Column(String(128), nullable=False, index=True)

    status = Column(String(32), nullable=False, default="FAILED", index=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    payload_found = Column(Boolean, nullable=False, default=False)
    vector_found = Column(Boolean, nullable=False, default=False)
    chunk_id_match = Column(Boolean, nullable=False, default=False)
    knowledge_base_id_match = Column(Boolean, nullable=False, default=False)
    training_item_id_match = Column(Boolean, nullable=False, default=False)
    vector_hash_match = Column(Boolean, nullable=False, default=False)
    payload_valid = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    metadata_json = Column(JSONB, nullable=False, default=dict)


__all__ = ["IndexVerificationItem"]
