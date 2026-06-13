from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class ProcessingMetrics(TenantSchemaBase):
    __tablename__ = "kb_processing_metrics"
    __table_args__ = (UniqueConstraint("knowledge_base_id", name="uq_kb_processing_metrics_kb"),)

    id = Column(String(64), primary_key=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    documents_total = Column(Integer, nullable=False, default=0)
    documents_ingested = Column(Integer, nullable=False, default=0)
    documents_understanding_ready = Column(Integer, nullable=False, default=0)
    documents_discovery_ready = Column(Integer, nullable=False, default=0)
    documents_indexed = Column(Integer, nullable=False, default=0)
    documents_failed = Column(Integer, nullable=False, default=0)
    documents_partial = Column(Integer, nullable=False, default=0)
    batches_total = Column(Integer, nullable=False, default=0)
    items_total = Column(Integer, nullable=False, default=0)
    extracted_parts_total = Column(Integer, nullable=False, default=0)
    normalized_parts_total = Column(Integer, nullable=False, default=0)
    chunks_total = Column(Integer, nullable=False, default=0)
    issues_open = Column(Integer, nullable=False, default=0)
    issues_warning = Column(Integer, nullable=False, default=0)
    issues_error = Column(Integer, nullable=False, default=0)
    issues_critical = Column(Integer, nullable=False, default=0)
    last_ingested_at = Column(DateTime, nullable=True)
    last_processed_at = Column(DateTime, nullable=True)
    last_failed_at = Column(DateTime, nullable=True)
    last_indexed_at = Column(DateTime, nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["ProcessingMetrics"]
