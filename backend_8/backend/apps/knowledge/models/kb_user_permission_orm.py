# Ez a fájl az adott terület adatmodelljeit és kapcsolódó struktúráit tartalmazza.
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint

from .base import TenantSchemaBase
from .utils import _utcnow_naive

class KbUserPermissionORM(TenantSchemaBase):
    """Tudástár–felhasználó jogosultság: use = használhatja (chat), train = taníthatja."""
    __tablename__ = "kb_user_permission"
    __table_args__ = (UniqueConstraint("kb_id", "user_id", name="uq_kb_user_permission_kb_user"),)

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = Column(String(10), nullable=False)  # 'use' | 'train'
    created_at = Column(DateTime, default=_utcnow_naive)
    created_by = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive)
    updated_by = Column(Integer, nullable=False)
