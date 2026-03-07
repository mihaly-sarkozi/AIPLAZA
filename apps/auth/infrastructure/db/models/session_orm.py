# apps/auth/infrastructure/db/models/session_orm.py
# ORM modell: refresh_tokens tábla.
# 2026.03.07 - Sárközi Mihály

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index

from apps.auth.infrastructure.db.models.base import AuthBase


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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        Index("ix_refresh_user_valid", "user_id", "valid"),
        Index("ix_refresh_token_hash", "token_hash"),  # logout invalidate_by_hash
    )
