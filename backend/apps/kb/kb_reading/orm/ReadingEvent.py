from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from shared.utils.clock import utc_now_naive
from core.kernel.db.model_bases import TenantSchemaBase


class ReadingEvent(TenantSchemaBase):
    __tablename__ = "kb_reading_events"

    id = Column(String(36), primary_key=True)
    reading_batch_id = Column(String(36), nullable=False, index=True)
    reading_item_id = Column(String(36), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    message = Column(Text, nullable=False, default="")
    details_json = Column("details", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)


__all__ = ["ReadingEvent"]
