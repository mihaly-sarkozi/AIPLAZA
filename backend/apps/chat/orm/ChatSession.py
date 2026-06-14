from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class ChatSession(TenantSchemaBase):
    __tablename__ = "chat_sessions"

    id = Column(String(64), primary_key=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    channel_id = Column(String(64), nullable=True, index=True)
    external_session_id = Column(String(128), nullable=True, index=True)
    knowledge_base_id = Column(String(64), nullable=True, index=True)
    kb_uuid = Column(String(64), nullable=True, index=True)

    status = Column(String(32), nullable=False, default="active", index=True)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)
    last_message_at = Column(DateTime, nullable=True)

    metadata_json = Column(JSONB, nullable=False, default=dict)


__all__ = ["ChatSession"]
