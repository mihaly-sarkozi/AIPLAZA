from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class IndexingJob(TenantSchemaBase):
    __tablename__ = "kb_indexing_jobs"

    id = Column(String(64), primary_key=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    knowledge_base_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    understanding_job_id = Column(String(64), nullable=False, index=True)
    discovery_job_id = Column(String(64), nullable=False, index=True)
    embedding_job_id = Column(String(64), nullable=False, index=True)

    status = Column(String(32), nullable=False, default="PENDING", index=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    collection_name = Column(String(128), nullable=False, default="")
    vector_size = Column(Integer, nullable=False, default=0)
    distance_metric = Column(String(32), nullable=False, default="cosine")

    chunks_total = Column(Integer, nullable=False, default=0)
    chunks_indexed = Column(Integer, nullable=False, default=0)
    chunks_failed = Column(Integer, nullable=False, default=0)

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)
    metadata_json = Column(JSONB, nullable=False, default=dict)


__all__ = ["IndexingJob"]
