from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class SearchQueryRun(TenantSchemaBase):
    __tablename__ = "kb_search_query_runs"

    id = Column(String(64), primary_key=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    channel_id = Column(String(64), nullable=True, index=True)
    conversation_id = Column(String(64), nullable=True, index=True)

    knowledge_base_id = Column(String(64), nullable=False, index=True)
    kb_uuid = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=True, index=True)

    question = Column(Text, nullable=False, default="")
    normalized_question = Column(Text, nullable=False, default="")
    rewritten_question = Column(Text, nullable=True)
    language_code = Column(String(16), nullable=True)

    search_mode = Column(String(32), nullable=False, default="hybrid")
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)

    query_embedding_model = Column(String(128), nullable=True)
    query_embedding_dimension = Column(Integer, nullable=True)

    top_k = Column(Integer, nullable=False, default=10)
    filters_json = Column(JSONB, nullable=False, default=dict)
    ranking_config_json = Column(JSONB, nullable=False, default=dict)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    metadata_json = Column(JSONB, nullable=False, default=dict)


__all__ = ["SearchQueryRun"]
