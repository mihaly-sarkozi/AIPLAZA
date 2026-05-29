# backend/core/modules/users/models/user_orm.py
# Feladat: A tenant schema users táblájának SQLAlchemy modellje.

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String

from core.kernel.db.model_bases import TenantSchemaBase
from core.kernel.runtime.clock import utc_now


class UserORM(TenantSchemaBase):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), nullable=False, server_default="user")
    created_at = Column(DateTime, default=utc_now)
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    updated_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, nullable=True)
    registration_completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    preferred_locale = Column(String(10), nullable=True)
    preferred_theme = Column(String(10), nullable=True)
    security_version = Column(Integer, default=0, nullable=False)
    credentials_password_set = Column(Boolean, default=True, nullable=False, server_default="true")
    pending_email = Column(String(255), nullable=True)
    pending_email_token_hash = Column(String(255), nullable=True, index=True)
    pending_email_expires_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_users_created_at", "created_at"),)
