# backend/core/modules/users/models/user_invite_token_orm.py
# Feladat: A tenant schema user_invite_tokens táblájának SQLAlchemy modellje.

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from core.kernel.db.model_bases import TenantSchemaBase
from core.kernel.runtime.clock import utc_now


class UserInviteTokenORM(TenantSchemaBase):
    __tablename__ = "user_invite_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    updated_by = Column(Integer, nullable=True)
