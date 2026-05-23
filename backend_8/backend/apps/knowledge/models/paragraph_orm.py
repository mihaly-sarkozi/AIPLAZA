from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeParagraphORM(TenantSchemaBase):
    __tablename__ = "knowledge_paragraphs"

    id = Column(String(36), primary_key=True)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    source_id = Column(String(36), nullable=False, index=True)
    document_id = Column(String(36), nullable=False, index=True)
    block_id = Column(String(36), nullable=True, index=True)
    order_index = Column(Integer, nullable=False, default=0)
    text_content = Column(Text, nullable=False, default="")
    char_start = Column(Integer, nullable=False, default=0)
    char_end = Column(Integer, nullable=False, default=0)
    sentence_count = Column(Integer, nullable=False, default=0)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
