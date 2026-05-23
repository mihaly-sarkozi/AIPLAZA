from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeSentenceORM(TenantSchemaBase):
    __tablename__ = "knowledge_sentences"

    id = Column(String(36), primary_key=True)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    source_id = Column(String(36), nullable=False, index=True)
    document_id = Column(String(36), nullable=False, index=True)
    paragraph_id = Column(String(36), nullable=False, index=True)
    order_index = Column(Integer, nullable=False, default=0)
    text_content = Column(Text, nullable=False, default="")
    char_start = Column(Integer, nullable=False, default=0)
    char_end = Column(Integer, nullable=False, default=0)
    token_count = Column(Integer, nullable=False, default=0)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
