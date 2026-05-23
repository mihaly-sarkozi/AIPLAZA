from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeParserRunORM(TenantSchemaBase):
    __tablename__ = "knowledge_parser_runs"

    id = Column(String(36), primary_key=True)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    source_id = Column(String(36), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    parser_type = Column(String(64), nullable=False, default="basic_text_v1")
    language = Column(String(16), nullable=True)
    error_message = Column(String(1024), nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, nullable=False, index=True)
    created_by = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
