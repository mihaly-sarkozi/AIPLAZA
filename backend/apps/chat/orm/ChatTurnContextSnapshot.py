from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class ChatTurnContextSnapshot(TenantSchemaBase):
    __tablename__ = "chat_turn_context_snapshots"

    id = Column(String(64), primary_key=True)
    turn_id = Column(String(64), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    query_run_id = Column(String(64), nullable=True, index=True)

    conversation_context_json = Column(JSONB, nullable=False, default=dict)
    search_context_json = Column(JSONB, nullable=False, default=dict)
    prompt_context_text = Column(Text, nullable=True)
    citations_json = Column(JSONB, nullable=False, default=list)
    sources_json = Column(JSONB, nullable=False, default=list)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)


__all__ = ["ChatTurnContextSnapshot"]
