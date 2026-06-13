from __future__ import annotations

# backend/apps/kb/kb_understanding/orm/StructuredBlock.py
# Feladat: A struktúrafelismerés egy blokkjának rekordja (structure detection kimenete).
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class StructuredBlock(TenantSchemaBase):
    __tablename__ = "kb_structured_blocks"

    # Egyedi azonosító (und_block_…).
    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    training_item_id = Column(String(64), nullable=False, index=True)
    knowledge_base_id = Column(String(36), nullable=False, index=True)
    # StructuredBlockType érték.
    block_type = Column(String(32), nullable=False, index=True)
    text = Column(Text, nullable=False, default="")
    # Sorrend a dokumentumon belül.
    order_index = Column(Integer, nullable=False, default=0, index=True)
    # Forráshely.
    page_number = Column(Integer, nullable=True)
    # A blokkot tartalmazó szakasz címe (legközelebbi heading).
    section_title = Column(String(512), nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["StructuredBlock"]
