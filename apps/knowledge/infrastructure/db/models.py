from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from apps.auth.infrastructure.db.models.base import TenantSchemaBase


class KBORM(TenantSchemaBase):
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True)
    uuid = Column(String(36), unique=True, nullable=False, index=True)
    name = Column(String(20), unique=True, nullable=False)
    description = Column(String(1024))
    qdrant_collection_name = Column(String(128), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
