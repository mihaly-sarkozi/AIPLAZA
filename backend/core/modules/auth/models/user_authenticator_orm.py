# backend/core/modules/auth/models/user_authenticator_orm.py
# Feladat: A tenant sémában tárolt authenticator/TOTP beállítás ORM modellje.

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint

from core.kernel.db.model_bases import AuthBase
from core.kernel.runtime.clock import utc_now


class UserAuthenticatorORM(AuthBase):
    __tablename__ = "user_authenticators"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_authenticator_user"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    secret_base32 = Column(String(128), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=False)
    pending_secret_base32 = Column(String(128), nullable=True)
    pending_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    updated_by = Column(Integer, nullable=True)
