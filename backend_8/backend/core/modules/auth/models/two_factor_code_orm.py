# backend/core/modules/auth/models/two_factor_code_orm.py
# Feladat: A tenant sémában tárolt emailes 2FA kód ORM modellje.

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String

from core.kernel.db.model_bases import AuthBase
from core.kernel.runtime.clock import utc_now


class TwoFactorCodeORM(AuthBase):
    __tablename__ = "two_factor_codes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    code_hash = Column(String(64), nullable=False)
    email = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    updated_by = Column(Integer, nullable=False)
    __table_args__ = (
        Index("ix_2fa_user_expires", "user_id", "expires_at"),
        Index("ix_2fa_user_code_hash", "user_id", "code_hash"),
    )
