from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeSourceORM(TenantSchemaBase):
    __tablename__ = "knowledge_sources"

    id = Column(String(36), primary_key=True)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    source_type = Column(String(32), nullable=False)
    raw_content = Column(Text, nullable=True)
    file_ref = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    created_by = Column(Integer, nullable=True)

