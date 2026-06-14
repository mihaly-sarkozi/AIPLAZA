from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class IndexVerification(TenantSchemaBase):
    __tablename__ = "kb_index_verifications"

    id = Column(String(64), primary_key=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    knowledge_base_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    indexing_job_id = Column(String(64), nullable=False, index=True)

    status = Column(String(32), nullable=False, default="PENDING", index=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    collection_name = Column(String(128), nullable=False, default="")
    expected_points = Column(Integer, nullable=False, default=0)
    verified_points = Column(Integer, nullable=False, default=0)
    missing_points = Column(Integer, nullable=False, default=0)
    payload_mismatches = Column(Integer, nullable=False, default=0)
    vector_hash_mismatches = Column(Integer, nullable=False, default=0)
    failed_points = Column(Integer, nullable=False, default=0)

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)

    metadata_json = Column(JSONB, nullable=False, default=dict)


__all__ = ["IndexVerification"]
