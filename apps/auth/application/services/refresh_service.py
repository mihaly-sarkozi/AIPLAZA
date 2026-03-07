# apps/auth/application/services/refresh_service.py
# Frissíti az eléréshez szükséges tokent, ha az lejárt.
# Security logolással a hamis vagy visszaélt tokenek észlelésére.
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations

import jwt
from datetime import datetime, timezone
from apps.auth.ports import SessionRepositoryInterface
from apps.core.security.token_service import TokenService
from apps.auth.domain.session import Session
from apps.core.security.security_logger import SecurityLogger
from apps.audit.application.audit_service import AuditService
from apps.core.security.permissions_changed_store import get as permissions_changed_get


class RefreshService:
    def __init__(
        self,
        session_repository: SessionRepositoryInterface,
        tokens: TokenService,
        logger: SecurityLogger,
        audit_service: AuditService,
    ):
        self.session_repository = session_repository
        self.tokens = tokens
        self.logger = logger
        self.audit = audit_service

    def refresh(self, refresh_token: str, ip: str | None, ua: str | None, tenant_slug: str | None = None):
        # -------------------------------
        # 1️⃣ Token dekódolása
        # -------------------------------
        try:
            payload = self.tokens.verify(refresh_token)

        except jwt.ExpiredSignatureError:
            self.logger.refresh_expired_token(ip, ua)
            self.audit.log("refresh_failed", user_id=None, details={"reason": "expired_token"}, ip=ip, user_agent=ua)
            return None

        except (jwt.InvalidSignatureError, jwt.DecodeError):
            self.logger.refresh_invalid_token(ip, ua)
            self.audit.log("refresh_failed", user_id=None, details={"reason": "invalid_token"}, ip=ip, user_agent=ua)
            return None

        if payload.get("typ") != "refresh":
            self.logger.refresh_wrong_type(ip, ua)
            self.audit.log("refresh_failed", user_id=None, details={"reason": "wrong_type"}, ip=ip, user_agent=ua)
            return None

        user_id = int(payload["sub"])
        jti = payload.get("jti")

        rec = self.session_repository.get_by_jti(jti)

        if rec is None:
            self.logger.refresh_unknown_jti(user_id, ip, ua)
            self.audit.log("refresh_failed", user_id=user_id, details={"reason": "unknown_jti"}, ip=ip, user_agent=ua)
            return None

        if not rec.valid:
            if permissions_changed_get(tenant_slug, rec.user_id):
                self.audit.log("refresh_failed", user_id=user_id, details={"reason": "permissions_changed"}, ip=ip, user_agent=ua)
                return (None, "permissions_changed")
            self.logger.refresh_reuse_detected(user_id, ip, ua)
            self.audit.log("refresh_failed", user_id=user_id, details={"reason": "reuse_detected"}, ip=ip, user_agent=ua)
            self.session_repository.invalidate_all_for_user(rec.user_id)
            return None

        if rec.is_expired():
            self.session_repository.update(rec.invalidate())
            self.logger.refresh_session_expired(user_id, ip, ua)
            self.audit.log("refresh_failed", user_id=user_id, details={"reason": "session_expired"}, ip=ip, user_agent=ua)
            return None

        # -------------------------------
        # 3️⃣ Token rotation
        # -------------------------------
        self.session_repository.update(rec.invalidate())

        # -------------------------------
        # 4️⃣ Új refresh token + session (auto_login továbbítás: aktivitásnál cookie kitolódik)
        # -------------------------------
        auto_login = payload.get("al", False)
        new_refresh, new_claims = self.tokens.make_refresh_pair(user_id, auto_login=auto_login)
        new_hash = self.tokens.hash_token(new_refresh)

        exp = new_claims["exp"]
        exp_dt = exp if isinstance(exp, datetime) else datetime.fromtimestamp(exp, tz=timezone.utc)

        new_sess = Session.new(
            user_id=user_id,
            jti=new_claims["jti"],
            token_hash=new_hash,
            expires_at=exp_dt,
            ip=ip,
            user_agent=ua,
        )
        self.session_repository.create(new_sess)

        # -------------------------------
        # 5️⃣ Új access token (jti a token_allowlisthez)
        # -------------------------------
        new_access, access_jti = self.tokens.make_access(user_id)

        self.logger.refresh_success(user_id, ip, ua)
        self.audit.log("refresh", user_id=user_id, ip=ip, user_agent=ua)

        return new_access, new_refresh, access_jti
