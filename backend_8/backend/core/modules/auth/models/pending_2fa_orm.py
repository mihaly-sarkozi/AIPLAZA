# backend/core/modules/auth/models/pending_2fa_orm.py
# Feladat: A tenant sémában tárolt pending 2FA login token ORM modellje.

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from core.kernel.db.model_bases import AuthBase
from core.kernel.runtime.clock import utc_now


class Pending2FAORM(AuthBase):
    __tablename__ = "pending_2fa_logins"
    id = Column(Integer, primary_key=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(Integer, nullable=False)
