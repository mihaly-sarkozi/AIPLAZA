from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class SearchQueryResult(TenantSchemaBase):
    __tablename__ = "kb_search_query_results"

    id = Column(String(64), primary_key=True)
    query_run_id = Column(String(64), nullable=False, index=True)

    knowledge_base_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    embedding_id = Column(String(64), nullable=True, index=True)
    qdrant_collection = Column(String(128), nullable=False, default="")
    qdrant_point_id = Column(String(128), nullable=False, index=True)

    rank = Column(Integer, nullable=False, default=0)
    qdrant_score = Column(Float, nullable=False, default=0.0)
    hybrid_score = Column(Float, nullable=False, default=0.0)
    overall_score = Column(Float, nullable=False, default=0.0)

    payload_json = Column(JSONB, nullable=False, default=dict)
    metadata_json = Column(JSONB, nullable=False, default=dict)

    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)


__all__ = ["SearchQueryResult"]
