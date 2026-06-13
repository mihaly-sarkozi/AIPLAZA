from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class ProcessMention(TenantSchemaBase):
    __tablename__ = "kb_process_mentions"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    process_name = Column(String(256), nullable=False, default="")
    step_text = Column(String(1024), nullable=False, default="")
    step_order = Column(Integer, nullable=True)
    responsibility = Column(String(256), nullable=True)
    input_hint = Column(String(512), nullable=True)
    output_hint = Column(String(512), nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
    is_optional = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=False, default=0.0)
    language_code = Column(String(8), nullable=True, index=True)
    recognizer_name = Column(String(64), nullable=False, default="")
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["ProcessMention"]
