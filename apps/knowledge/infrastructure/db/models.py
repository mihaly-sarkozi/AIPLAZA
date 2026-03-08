from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
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


class KbUserPermissionORM(TenantSchemaBase):
    """Tudástár–felhasználó jogosultság: use = használhatja (chat), train = taníthatja."""
    __tablename__ = "kb_user_permission"
    __table_args__ = (UniqueConstraint("kb_id", "user_id", name="uq_kb_user_permission_kb_user"),)

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = Column(String(10), nullable=False)  # 'use' | 'train'
