# backend/admin/domain/admin_models.py
# Feladat: A platform-admin funkció public schema ORM modelljeit definiálja. Tartalmazza az admin felhasználókat, invite tokeneket, refresh sessionöket, MFA próbálkozásokat, security alert sorokat és IP tiltásokat. Admin domain/perzisztencia modellréteg, amelyet a repository kezel.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from core.kernel.runtime.clock import utc_now
from core.kernel.db.model_bases import PublicBase


class PlatformAdminUserORM(PublicBase):
    __tablename__ = "platform_admin_users"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    role = Column(String(20), nullable=False, default="admin")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    updated_by = Column(Integer, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(Integer, nullable=True)
    registration_completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    security_version = Column(Integer, nullable=False, default=0)
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    mfa_secret_base32 = Column(String(128), nullable=True)
    mfa_pending_secret_base32 = Column(String(128), nullable=True)
    mfa_pending_expires_at = Column(DateTime(timezone=True), nullable=True)
    mfa_recovery_codes_hashes = Column(String, nullable=False, default="[]")


class PlatformAdminInviteTokenORM(PublicBase):
    __tablename__ = "platform_admin_invite_tokens"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("public.platform_admin_users.id"), nullable=False, index=True)
    token_hash = Column(String(255), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    updated_by = Column(Integer, nullable=True)


class PlatformAdminRefreshTokenORM(PublicBase):
    __tablename__ = "platform_admin_refresh_tokens"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("public.platform_admin_users.id"), nullable=False, index=True)
    jti = Column(String(128), nullable=False, unique=True, index=True)
    token_hash = Column(String(255), nullable=False, index=True)
    ip = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    valid = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    updated_by = Column(Integer, nullable=True)


class PlatformSecurityIpBanORM(PublicBase):
    __tablename__ = "platform_security_ip_bans"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True)
    ip = Column(String(64), nullable=False, unique=True, index=True)
    reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    created_by = Column(Integer, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    released_by = Column(Integer, nullable=True)


class PlatformSecurityAlertORM(PublicBase):
    __tablename__ = "platform_security_alerts"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True)
    alert_key = Column(String(255), nullable=False, unique=True, index=True)
    category = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, index=True)
    signal = Column(String(255), nullable=False)
    title = Column(String(255), nullable=False)
    value = Column(Integer, nullable=False, default=0)
    hit_count = Column(Integer, nullable=False, default=1)
    status = Column(String(16), nullable=False, default="open", index=True)
    first_seen_at = Column(DateTime(timezone=True), default=utc_now)
    last_seen_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    updated_by = Column(Integer, nullable=True)


class PlatformAdminMfaAttemptORM(PublicBase):
    __tablename__ = "platform_admin_mfa_attempts"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True)
    scope = Column(String(32), nullable=False, index=True)  # totp_user, totp_ip, recovery_user, recovery_ip
    scope_key = Column(String(128), nullable=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    window_started_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    blocked_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    created_by = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    updated_by = Column(Integer, nullable=True)
