from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class ProcessingIssue(TenantSchemaBase):
    __tablename__ = "kb_processing_issues"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_base_id",
            "training_item_id",
            "module",
            "stage",
            "issue_code",
            name="uq_kb_processing_issues_dedup",
        ),
    )

    id = Column(String(64), primary_key=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    training_batch_id = Column(String(64), nullable=True, index=True)
    training_item_id = Column(String(64), nullable=True, index=True)
    job_id = Column(String(64), nullable=True, index=True)
    module = Column(String(64), nullable=False, index=True)
    stage = Column(String(64), nullable=False, index=True)
    step = Column(String(64), nullable=True, index=True)
    severity = Column(String(16), nullable=False, index=True)
    issue_code = Column(String(64), nullable=False, index=True)
    issue_message = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="OPEN", index=True)
    first_seen_at = Column(DateTime, default=utc_now_naive, nullable=False)
    last_seen_at = Column(DateTime, default=utc_now_naive, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    occurrence_count = Column(Integer, nullable=False, default=1)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)


__all__ = ["ProcessingIssue"]
