from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class DiscoveryStepRun(TenantSchemaBase):
    __tablename__ = "kb_discovery_step_runs"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    step = Column(String(32), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="completed", index=True)
    input_summary = Column(JSONB, nullable=False, default=dict)
    output_summary = Column(JSONB, nullable=False, default=dict)
    duration_ms = Column(Integer, nullable=False, default=0)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)


__all__ = ["DiscoveryStepRun"]
