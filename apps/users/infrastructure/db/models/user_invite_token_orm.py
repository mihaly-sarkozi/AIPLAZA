# apps/users/infrastructure/db/models/user_invite_token_orm.py
# Jelszó beállító link tokenek (admin user létrehozás után, 24h érvényes).
# 2026.03.07 - Sárközi Mihály

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from apps.auth.infrastructure.db.models.base import TenantSchemaBase


class UserInviteTokenORM(TenantSchemaBase):
    __tablename__ = "user_invite_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
