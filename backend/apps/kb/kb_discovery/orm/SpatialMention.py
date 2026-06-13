from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class SpatialMention(TenantSchemaBase):
    __tablename__ = "kb_spatial_mentions"

    id = Column(String(64), primary_key=True)
    job_id = Column(String(64), nullable=False, index=True)
    chunk_id = Column(String(64), nullable=False, index=True)
    raw_text = Column(String(512), nullable=False)
    normalized_location = Column(String(512), nullable=False)
    location_type = Column(String(32), nullable=False, index=True)
    site_id = Column(String(64), nullable=True)
    geo_lat = Column(Float, nullable=True)
    geo_lng = Column(Float, nullable=True)
    confidence = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=utc_now_naive, nullable=False)


__all__ = ["SpatialMention"]
