# apps/auth/infrastructure/db/models/pending_2fa_orm.py
# ORM: pending_2fa_logins – 2FA 1. lépés után ide kerül a token (2. lépésben consume).
# 2026.03.07 - Sárközi Mihály

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from apps.auth.infrastructure.db.models.base import AuthBase


class Pending2FAORM(AuthBase):
    __tablename__ = "pending_2fa_logins"
    id = Column(Integer, primary_key=True)
    token = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
