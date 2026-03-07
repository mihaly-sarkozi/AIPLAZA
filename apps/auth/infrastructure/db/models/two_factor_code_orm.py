# apps/auth/infrastructure/db/models/two_factor_code_orm.py
# ORM modell: two_factor_codes tábla.
# 2026.03.07 - Sárközi Mihály

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index

from apps.auth.infrastructure.db.models.base import AuthBase


class TwoFactorCodeORM(AuthBase):
    __tablename__ = "two_factor_codes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    code_hash = Column(String(64), nullable=False)  # SHA-256 hex; nyers OTP nincs tárolva
    email = Column(String(255), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        Index("ix_2fa_user_expires", "user_id", "expires_at"),
        Index("ix_2fa_user_code_hash", "user_id", "code_hash"),
    )
