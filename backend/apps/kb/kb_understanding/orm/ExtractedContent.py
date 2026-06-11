from __future__ import annotations

# backend/apps/kb/kb_understanding/orm/ExtractedContent.py
# Feladat: A forrásból kinyert nyers szöveg perzisztencia rekordja (extract lépés kimenete).
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class ExtractedContent(TenantSchemaBase):
    __tablename__ = "kb_extracted_content"

    # Egyedi azonosító (und_extract_…).
    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    # Kinyert teljes szöveg.
    text = Column(Text, nullable=False, default="")
    # Oldaltérkép: [{"page": 1, "start": 0, "end": 1234}, …] — forráshely visszavezetéshez.
    page_map = Column(JSONB, nullable=False, default=list)
    char_count = Column(Integer, nullable=False, default=0)
    # Forrás mime / extractor adapter neve.
    source_mime = Column(String(255), nullable=True)
    extractor = Column(String(64), nullable=False, default="")
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)


__all__ = ["ExtractedContent"]
