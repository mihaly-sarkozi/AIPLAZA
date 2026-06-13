from __future__ import annotations

# backend/apps/kb/kb_understanding/orm/NormalizedContent.py
# Feladat: A tisztított (normalizált) szöveg perzisztencia rekordja (normalize lépés kimenete).
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class NormalizedContent(TenantSchemaBase):
    __tablename__ = "kb_normalized_content"

    # Egyedi azonosító (und_norm_…).
    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    text = Column(Text, nullable=False, default="")
    # Normalizálás után érvényes oldaltérkép.
    page_map = Column(JSONB, nullable=False, default=list)
    # Forrás partok metaadat-térképe (offset + extract metadata).
    part_map = Column(JSONB, nullable=False, default=list)
    char_count = Column(Integer, nullable=False, default=0)
    # Alkalmazott normalizálási műveletek összegzése (pl. removed_lines, fixed_encoding).
    applied_rules = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)


__all__ = ["NormalizedContent"]
