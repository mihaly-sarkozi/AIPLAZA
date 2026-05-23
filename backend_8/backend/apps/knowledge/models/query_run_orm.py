from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeQueryRunORM(TenantSchemaBase):
    __tablename__ = "knowledge_query_runs"

    id = Column(String(36), primary_key=True)
    query_text = Column(Text, nullable=False)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    build_ids = Column(JSONB, nullable=False, default=list)
    retrieval_profile_key = Column(String(64), nullable=False)
    context_profile_key = Column(String(64), nullable=False)
    latency_ms = Column(Float, nullable=False, default=0.0)
    result_count = Column(Integer, nullable=False, default=0)
    citations = Column(JSONB, nullable=False, default=list)
    context_text = Column(Text, nullable=False, default="")
    feedback = Column(String(64), nullable=True)
    compare_mode = Column(Boolean, nullable=False, default=False)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False, index=True)

