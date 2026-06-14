from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class IndexRebuild(TenantSchemaBase):
    __tablename__ = "kb_index_rebuilds"

    id = Column(String(64), primary_key=True)
    tenant_slug = Column(String(64), nullable=True, index=True)
    knowledge_base_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    mode = Column(String(64), nullable=False, default="POINT_DELETE_AND_REINDEX")
    requested_by = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)

    training_items_total = Column(Integer, nullable=False, default=0)
    training_items_reindexed = Column(Integer, nullable=False, default=0)
    training_items_failed = Column(Integer, nullable=False, default=0)

    points_deleted = Column(Integer, nullable=False, default=0)
    points_reindexed = Column(Integer, nullable=False, default=0)
    points_verified = Column(Integer, nullable=False, default=0)

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive, nullable=False)


__all__ = ["IndexRebuild"]
