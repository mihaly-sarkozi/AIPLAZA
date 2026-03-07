# apps/auth/application/services/refresh_service.py
# Frissíti az eléréshez szükséges tokent, ha az lejárt.
# Security logolással a hamis vagy visszaélt tokenek észlelésére.
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING
import jwt
from datetime import datetime, timezone
from apps.auth.ports import SessionRepositoryInterface
from apps.core.security.token_service import TokenService
from apps.core.timing import record_span
from apps.auth.domain.session import Session
from apps.core.security.security_logger import SecurityLogger
from apps.audit.application.audit_service import AuditService
from apps.core.security.permissions_changed_store import get as permissions_changed_get

if TYPE_CHECKING:
    from apps.users.ports import UserRepositoryInterface


def _ctx(tenant_slug: Optional[str], correlation_id: Optional[str]) -> dict:
    return {"tenant_slug": tenant_slug, "correlation_id": correlation_id}


class RefreshService:
    def __init__(
        self,
        session_repository: SessionRepositoryInterface,
        tokens: TokenService,
        logger: SecurityLogger,
        audit_service: AuditService,
        user_repository: "UserRepositoryInterface | None" = None,
    ):
        self.session_repository = session_repository
        self.tokens = tokens
        self.logger = logger
        self.audit = audit_service
        self.user_repository = user_repository

    @staticmethod
    def _fingerprint_mismatch(rec: Session, ip: str | None, ua: str | None) -> bool:
        """True ha a session tárolt IP és user_agent mindkettő megvan, és mindkettő különbözik a jelenlegitől."""
        if rec.ip is None or rec.user_agent is None:
            return False
        current_ip = (ip or "").strip()
        current_ua = (ua or "").strip()
        stored_ip = (rec.ip or "").strip()
        stored_ua = (rec.user_agent or "").strip()
        if not stored_ip or not stored_ua:
            return False
        return current_ip != stored_ip and current_ua != stored_ua

    def refresh(
        self,
        refresh_token: str,
        ip: str | None,
        ua: str | None,
        tenant_slug: str | None = None,
        *,
        correlation_id: Optional[str] = None,
        tenant_security_version: int = 0,
    ):
        ctx = _ctx(tenant_slug, correlation_id)
        # -------------------------------
        # 1️⃣ Token dekódolása
        # -------------------------------
        t0_verify = time.monotonic()
        try:
            payload = self.tokens.verify(refresh_token)
            record_span("refresh_token_verify", (time.monotonic() - t0_verify) * 1000)
        except jwt.ExpiredSignatureError:
            self.logger.refresh_expired_token(ip, ua, **ctx)
            self.audit.log("refresh_failed", user_id=None, details={"reason": "expired_token"}, ip=ip, user_agent=ua, tenant_slug=tenant_slug)
            return None

        except (jwt.InvalidSignatureError, jwt.DecodeError):
            self.logger.refresh_invalid_token(ip, ua, **ctx)
            self.audit.log("refresh_failed", user_id=None, details={"reason": "invalid_token"}, ip=ip, user_agent=ua, tenant_slug=tenant_slug)
            return None

        if payload.get("typ") != "refresh":
            self.logger.refresh_wrong_type(ip, ua, **ctx)
            self.audit.log("refresh_failed", user_id=None, details={"reason": "wrong_type"}, ip=ip, user_agent=ua, tenant_slug=tenant_slug)
            return None

        user_id = int(payload["sub"])
        jti = payload.get("jti")
        token_user_ver = payload.get("user_ver", 0)
        token_tenant_ver = payload.get("tenant_ver", 0)

        # Security version: ha a token user_ver/tenant_ver nem egyezik a jelenlegivel, token bukik (force revoke)
        current_user_ver = token_user_ver
        user_for_ver = None
        if self.user_repository:
            t0_user = time.monotonic()
            user_for_ver = self.user_repository.get_by_id(user_id)
            record_span("refresh_user_ver_fetch", (time.monotonic() - t0_user) * 1000)
            current_user_ver = getattr(user_for_ver, "security_version", 0) if user_for_ver else 0
            if token_user_ver != current_user_ver or token_tenant_ver != tenant_security_version:
                self.logger.refresh_session_expired(user_id, ip, ua, **ctx)
                self.audit.log("refresh_failed", user_id=user_id, details={"reason": "security_version_mismatch"}, ip=ip, user_agent=ua, tenant_slug=tenant_slug)
                return None

        t0_sess = time.monotonic()
        rec = self.session_repository.get_by_jti(jti)
        record_span("refresh_session_lookup", (time.monotonic() - t0_sess) * 1000)

        if rec is None:
            self.logger.refresh_unknown_jti(user_id, ip, ua, **ctx)
            self.audit.log("refresh_failed", user_id=user_id, details={"reason": "unknown_jti"}, ip=ip, user_agent=ua, tenant_slug=tenant_slug)
            return None

        if not rec.valid:
            if permissions_changed_get(tenant_slug, rec.user_id):
                self.audit.log("refresh_failed", user_id=user_id, details={"reason": "permissions_changed"}, ip=ip, user_agent=ua, tenant_slug=tenant_slug)
                return (None, "permissions_changed")
            self.logger.refresh_reuse_detected(user_id, ip, ua, **ctx)
            self.audit.log("refresh_failed", user_id=user_id, details={"reason": "reuse_detected"}, ip=ip, user_agent=ua, tenant_slug=tenant_slug)
            self.session_repository.invalidate_all_for_user(rec.user_id)
            return None

        if rec.is_expired():
            self.session_repository.update(rec.invalidate())
            self.logger.refresh_session_expired(user_id, ip, ua, **ctx)
            self.audit.log("refresh_failed", user_id=user_id, details={"reason": "session_expired"}, ip=ip, user_agent=ua, tenant_slug=tenant_slug)
            return None

        # -------------------------------
        # 2b️⃣ Device/session binding: teljesen más fingerprint → gyanús, új 2FA kérés
        # -------------------------------
        if self._fingerprint_mismatch(rec, ip, ua):
            self.audit.log(
                "refresh_suspicious_fingerprint",
                user_id=user_id,
                details={
                    "reason": "fingerprint_mismatch",
                    "stored_ip": rec.ip,
                    "current_ip": ip,
                    "stored_ua": (rec.user_agent[:80] + "…") if rec.user_agent and len(rec.user_agent) > 80 else rec.user_agent,
                    "current_ua": (ua[:80] + "…") if ua and len(ua) > 80 else ua,
                },
                ip=ip,
                user_agent=ua,
                tenant_slug=tenant_slug,
            )
            return (None, "re_2fa_required")

        # -------------------------------
        # 3️⃣ Token rotation
        # -------------------------------
        self.session_repository.update(rec.invalidate())

        # -------------------------------
        # 4️⃣ Új refresh token + session (auto_login továbbítás; user_ver/tenant_ver = force revoke)
        # -------------------------------
        auto_login = payload.get("al", False)
        user_ver = current_user_ver
        tenant_ver = tenant_security_version
        new_refresh, new_claims = self.tokens.make_refresh_pair(user_id, auto_login=auto_login, user_ver=user_ver, tenant_ver=tenant_ver)
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
        # 5️⃣ Új access token (jti a token_allowlisthez; user_ver/tenant_ver = force revoke)
        # -------------------------------
        new_access, access_jti = self.tokens.make_access(user_id, user_ver=user_ver, tenant_ver=tenant_ver, role=getattr(user_for_ver, "role", "user"))

        self.logger.refresh_success(user_id, ip, ua, **ctx)
        self.audit.log("refresh", user_id=user_id, ip=ip, user_agent=ua, tenant_slug=tenant_slug)

        # user_for_ver már megvan (version check); visszaadjuk, hogy a route ne hívjon get_by_id-t újra (hot path optimalizáció)
        return new_access, new_refresh, access_jti, user_for_ver
