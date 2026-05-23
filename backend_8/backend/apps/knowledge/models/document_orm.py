from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeDocumentORM(TenantSchemaBase):
    __tablename__ = "knowledge_documents"

    id = Column(String(36), primary_key=True)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    source_id = Column(String(36), nullable=False, unique=True, index=True)
    parser_run_id = Column(String(36), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    language = Column(String(16), nullable=True)
    text_content = Column(Text, nullable=False, default="")
    char_count = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="draft", index=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, nullable=False, index=True)
