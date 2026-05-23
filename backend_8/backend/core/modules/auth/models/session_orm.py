# backend/core/modules/auth/models/session_orm.py
# Feladat: A tenant sémában tárolt refresh session ORM modellje.

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String

from core.kernel.db.model_bases import AuthBase
from core.kernel.runtime.clock import utc_now


class SessionORM(AuthBase):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    jti = Column(String(128), unique=True, index=True, nullable=False)
    token_hash = Column(String(255), nullable=False)
    ip = Column(String(64))
    user_agent = Column(String(255))
    valid = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    updated_by = Column(Integer, nullable=False)
    __table_args__ = (
        Index("ix_refresh_user_valid", "user_id", "valid"),
        Index("ix_refresh_token_hash", "token_hash"),
    )
