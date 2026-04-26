from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from .base import TenantSchemaBase
from .utils import _utcnow_naive


class KnowledgeIngestEventORM(TenantSchemaBase):
    __tablename__ = "knowledge_ingest_events"

    id = Column(String(36), primary_key=True)
    ingest_run_id = Column(String(36), nullable=False, index=True)
    ingest_item_id = Column(String(36), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="info")
    message = Column(String(1024), nullable=True)
    details_json = Column("details", JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False, index=True)
    created_by = Column(Integer, nullable=True)
