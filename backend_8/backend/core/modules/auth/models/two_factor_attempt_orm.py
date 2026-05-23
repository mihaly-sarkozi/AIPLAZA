# backend/core/modules/auth/models/two_factor_attempt_orm.py
# Feladat: A tenant sémában tárolt 2FA próbálkozásszámláló ORM modellje.

from __future__ import annotations

from sqlalchemy import Column, DateTime, Index, Integer, String

from core.kernel.db.model_bases import AuthBase
from core.kernel.runtime.clock import utc_now


class TwoFactorAttemptORM(AuthBase):
    __tablename__ = "two_factor_attempts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(20), nullable=False)
    scope_key = Column(String(128), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    window_start_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(Integer, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    updated_by = Column(Integer, nullable=False)
    __table_args__ = (
        Index("ix_2fa_attempt_scope_key", "scope", "scope_key", unique=True),
    )
