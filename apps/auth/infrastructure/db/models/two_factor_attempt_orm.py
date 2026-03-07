# apps/auth/infrastructure/db/models/two_factor_attempt_orm.py
# ORM: 2FA sikertelen próbálkozások (brute-force védelem: token / user / IP alapú limit).
# 2026.03 - Sárközi Mihály

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Index

from apps.auth.infrastructure.db.models.base import AuthBase


class TwoFactorAttemptORM(AuthBase):
    __tablename__ = "two_factor_attempts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    scope = Column(String(20), nullable=False)  # 'token' | 'user' | 'ip'
    scope_key = Column(String(128), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    window_start_at = Column(DateTime, nullable=False)
    __table_args__ = (
        Index("ix_2fa_attempt_scope_key", "scope", "scope_key", unique=True),
    )
