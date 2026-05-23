from sqlalchemy import BigInteger, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeIngestInputORM(TenantSchemaBase):
    __tablename__ = "knowledge_ingest_inputs"

    id = Column(String(36), primary_key=True)
    ingest_item_id = Column(String(36), nullable=False, unique=True, index=True)
    input_type = Column(String(16), nullable=False, index=True)
    storage_provider = Column(String(64), nullable=True)
    bucket_name = Column(String(255), nullable=True)
    object_key = Column(String(1024), nullable=True)
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(255), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    text_content = Column(Text, nullable=True)
    origin_url = Column(String(1024), nullable=True)
    external_ref = Column(String(255), nullable=True)
    checksum_sha256 = Column(String(128), nullable=True, index=True)
    encoding = Column(String(64), nullable=True)
    language_hint = Column(String(32), nullable=True)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)
