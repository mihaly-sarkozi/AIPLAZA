from sqlalchemy import Column, DateTime, Float, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeSentenceInterpretationORM(TenantSchemaBase):
    __tablename__ = "knowledge_sentence_interpretations"

    id = Column(String(36), primary_key=True)
    corpus_uuid = Column(String(36), nullable=False, index=True)
    source_id = Column(String(36), nullable=False, index=True)
    document_id = Column(String(36), nullable=False, index=True)
    sentence_id = Column(String(36), nullable=False, unique=True, index=True)
    interpretation_run_id = Column(String(36), nullable=False, index=True)
    sentence_text = Column(Text, nullable=False, default="")
    claim_summary = Column(Text, nullable=False, default="")
    assertion_mode = Column(String(32), nullable=False, default="fact", index=True)
    claim_type = Column(String(32), nullable=False, default="other", index=True)
    time_mode = Column(String(32), nullable=False, default="unknown", index=True)
    time_label = Column(String(128), nullable=True)
    space_mode = Column(String(32), nullable=False, default="unknown", index=True)
    space_label = Column(String(128), nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    metadata_json = Column("metadata", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, nullable=False, index=True)
