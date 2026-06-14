from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class SearchContextBlock(TenantSchemaBase):
    __tablename__ = "kb_search_context_blocks"

    id = Column(String(64), primary_key=True)
    query_run_id = Column(String(64), nullable=False, index=True)

    context_block_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    source_id = Column(String(128), nullable=False, default="")

    rank = Column(Integer, nullable=False, default=0)
    included_in_prompt = Column(Integer, nullable=False, default=1)
    token_estimate = Column(Integer, nullable=True)

    text = Column(Text, nullable=False, default="")
    snippet = Column(Text, nullable=False, default="")
    heading_path = Column(String(512), nullable=True)
    section_title = Column(String(512), nullable=True)
    page_numbers = Column(JSONB, nullable=False, default=list)

    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)


__all__ = ["SearchContextBlock"]
