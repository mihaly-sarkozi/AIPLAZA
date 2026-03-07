# apps/users/infrastructure/db/models/user_orm.py
# ORM: users tábla, tenantonként külön séma (pl. demo.users). Base = auth TenantSchemaBase (séma create_all).
# 2026.03.07 - Sárközi Mihály

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Index

from apps.auth.infrastructure.db.models.base import TenantSchemaBase


class UserORM(TenantSchemaBase):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), nullable=False, server_default="user")  # user | admin | owner
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    registration_completed_at = Column(DateTime(timezone=True), nullable=True)  # set when user sets password via invite
    failed_login_attempts = Column(Integer, default=0, nullable=False)  # 5 sikertelen → is_active=False (admin újraküldi a linket)
    preferred_locale = Column(String(10), nullable=True)   # hu | en | es
    preferred_theme = Column(String(10), nullable=True)    # light | dark
    __table_args__ = (Index("ix_users_created_at", "created_at"),)  # list_all order_by
