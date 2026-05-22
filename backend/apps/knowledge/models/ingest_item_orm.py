from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeIngestItemORM(TenantSchemaBase):
    __tablename__ = "knowledge_ingest_items"

    id = Column(String(36), primary_key=True)
    ingest_run_id = Column(String(36), nullable=False, index=True)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    queue_order = Column(Integer, nullable=False, default=0)
    input_type = Column(String(16), nullable=False, index=True)
    display_name = Column(String(255), nullable=False)
    title = Column(String(200), nullable=False)
    origin = Column(String(1024), nullable=True)
    status = Column(String(32), nullable=False, default="received", index=True)
    progress_message = Column(String(512), nullable=True)
    result_message = Column(String(512), nullable=True)
    error_code = Column(String(128), nullable=True)
    error_message = Column(String(1024), nullable=True)
    duplicate_of_item_id = Column(String(36), nullable=True)
    duplicate_of_source_id = Column(String(36), nullable=True)
    pipeline_route = Column(String(64), nullable=False, default="source_parser")
    pipeline_version = Column(String(64), nullable=False, default="source_parser.v1", index=True)
    idempotency_key = Column(String(192), nullable=True, index=True)
    parser_job_id = Column(String(64), nullable=True)
    source_id = Column(String(36), nullable=True)
    content_hash = Column(String(128), nullable=True, index=True)
    lease_owner = Column(String(128), nullable=True, index=True)
    lease_expires_at = Column(DateTime, nullable=True, index=True)
    heartbeat_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    max_retries = Column(Integer, nullable=False, default=3)
    dead_letter_reason = Column(String(1024), nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)
    created_by = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
