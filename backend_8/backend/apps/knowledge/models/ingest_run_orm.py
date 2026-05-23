from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeIngestRunORM(TenantSchemaBase):
    __tablename__ = "knowledge_ingest_runs"

    id = Column(String(36), primary_key=True)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    input_channel = Column(String(32), nullable=False, default="manual")
    status = Column(String(32), nullable=False, default="received", index=True)
    batch_size = Column(Integer, nullable=False, default=0)
    queued_count = Column(Integer, nullable=False, default=0)
    processing_count = Column(Integer, nullable=False, default=0)
    completed_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)
    duplicate_count = Column(Integer, nullable=False, default=0)
    rejected_count = Column(Integer, nullable=False, default=0)
    continue_on_error = Column(Boolean, nullable=False, default=True)
    pipeline_route = Column(String(64), nullable=False, default="source_parser")
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)
    created_by = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
