from __future__ import annotations

# backend/apps/kb/kb_crud/orm/KnowledgeBasePermissionORM.py
# Feladat: Tudástár–felhasználó jogosultság perzisztencia — a `kb_user_permission` tábla ORM definíciója.
# Sárközi Mihály - 2026.06.11

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from core.kernel.db.model_bases import TenantSchemaBase
from shared.utils.clock import utc_now_naive


class KnowledgeBasePermissionORM(TenantSchemaBase):
    """Tudástár–felhasználó jogosultság: ``use`` = használhatja (chat), ``train`` = taníthatja.

    A ``none`` jogosultság nincs eltárolva — annak a sornak a hiánya jelenti.
    """

    __tablename__ = "kb_user_permission"
    __table_args__ = (UniqueConstraint("kb_id", "user_id", name="uq_kb_user_permission_kb_user"),)

    id = Column(Integer, primary_key=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = Column(String(10), nullable=False)
    created_at = Column(DateTime, default=utc_now_naive)
    created_by = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=utc_now_naive, onupdate=utc_now_naive)
    updated_by = Column(Integer, nullable=False)


__all__ = ["KnowledgeBasePermissionORM"]
