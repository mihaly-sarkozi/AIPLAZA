from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class ChatTurn(TenantSchemaBase):
    __tablename__ = "chat_turns"

    id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    role = Column(String(16), nullable=False, index=True)
    message_text = Column(Text, nullable=False, default="")

    query_run_id = Column(String(64), nullable=True, index=True)
    answer_mode = Column(String(32), nullable=True)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)


__all__ = ["ChatTurn"]
