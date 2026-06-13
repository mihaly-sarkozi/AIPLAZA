from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class EntityMention(TenantSchemaBase):
    __tablename__ = "kb_entity_mentions"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(64), nullable=True, index=True)
    training_item_id = Column(String(64), nullable=True, index=True)
    entity_type = Column(String(32), nullable=False, index=True)
    raw_text = Column(String(512), nullable=False)
    normalized_name = Column(String(512), nullable=False, index=True)
    start_offset = Column(Integer, nullable=False, default=0)
    end_offset = Column(Integer, nullable=False, default=0)
    confidence = Column(Float, nullable=False, default=0.0)
    source = Column(String(64), nullable=True)
    language_code = Column(String(16), nullable=True)
    subtype = Column(String(64), nullable=True)
    recognizer_name = Column(String(64), nullable=True)
    page_numbers = Column(JSONB, nullable=False, default=list)
    source_part_ids = Column(JSONB, nullable=False, default=list)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["EntityMention"]
