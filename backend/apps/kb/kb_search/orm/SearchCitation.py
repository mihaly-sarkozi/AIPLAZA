from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class SearchCitation(TenantSchemaBase):
    __tablename__ = "kb_search_citations"

    id = Column(String(64), primary_key=True)
    query_run_id = Column(String(64), nullable=False, index=True)

    citation_id = Column(String(32), nullable=False, index=True)
    source_id = Column(String(128), nullable=False, default="")
    chunk_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    document_title = Column(String(512), nullable=False, default="")
    document_type = Column(String(64), nullable=True)
    page_numbers = Column(JSONB, nullable=False, default=list)
    section_title = Column(String(512), nullable=True)

    snippet = Column(Text, nullable=False, default="")
    download_ref = Column(String(512), nullable=True)
    source_url = Column(String(1024), nullable=True)
    index_ref = Column(String(256), nullable=True)

    display_order = Column(Integer, nullable=False, default=0)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)


__all__ = ["SearchCitation"]
