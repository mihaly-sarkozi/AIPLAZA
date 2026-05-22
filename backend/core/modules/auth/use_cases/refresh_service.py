# backend/core/modules/auth/use_cases/refresh_service.py
# Feladat: Refresh tokenből új access/refresh tokent kiadó application service. Ellenőrzi a token típust, JTI-t, sessiont, token hasht, fingerprintet, user/tenant security verziót és jogosultságváltozás jelzést, majd rotálja a sessiont vagy okos hibareasonnel tér vissza. Auth use case réteg security loggal, audittal és metrikával.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING
import jwt
from datetime import datetime, timezone
from core.modules.auth.domain.dto import TenantAuthContext
from core.modules.auth.domain.ports import (
    AuthSessionRepositoryPort,
    AuthUserRepositoryPort,
    SecurityLoggerPort,
    TokenServicePort,
)
from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.kernel.logging.request_timing import record_span
from core.modules.auth.domain.dto.session import Session
from core.kernel.logging.security_logger import SecurityLogger
from core.infrastructure.audit.service.audit_service import AuditService
from core.modules.auth.repository.permissions_changed_store import get as permissions_changed_get
from core.kernel.db.transactional_service import TransactionalServiceMixin
from core.kernel.logging.observability import increment_metric
from core.modules.auth.use_cases.refresh_result import RefreshFailed, RefreshFailReason, RefreshSuccess, RefreshResult

if TYPE_CHECKING:
    from core.modules.users.repository.persistence import UserRepository


# Ez a függvény a(z) ctx logikáját valósítja meg.
def _ctx(tenant: TenantAuthContext | None) -> dict:
    return {
        "tenant_slug": tenant.slug if tenant else None,
        "correlation_id": tenant.correlation_id if tenant else None,
    }

# Authentikációhoz szükséges frissitő kulcs előállítása
class RefreshService(TransactionalServiceMixin):
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(
        self,
        session_repository: AuthSessionRepositoryPort,
        tokens: TokenServicePort,
        logger: SecurityLoggerPort | SecurityLogger,
        audit_service: AuditService,
        user_repository: "AuthUserRepositoryPort | UserRepository | None" = None,
        transaction_manager=None,
    ):
        super().__init__(transaction_manager=transaction_manager)
        self.session_repository = session_repository
        self.tokens = tokens
        self.logger = logger
        self.audit = audit_service
        self.user_repository = user_repository

    # Fingerprint ellenőrzés
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


    # Authentikációhoz szükséges frissitő kulcs előállítása
    def refresh(
        self,
        refresh_token: str,
        ip: str | None,
        ua: str | None,
        *,
        tenant: TenantAuthContext | None = None,
    ) -> RefreshResult:
        with self._transaction():
            ctx = _ctx(tenant)
            # -------------------------------
            # 1️⃣ Token dekódolása
            # -------------------------------
            t0_verify = time.monotonic()
            try:
                payload = self.tokens.verify(refresh_token)
                record_span("refresh_token_verify", (time.monotonic() - t0_verify) * 1000)
            except jwt.ExpiredSignatureError:
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "refresh", "reason": "expired_token"})
                self.logger.refresh_expired_token(ip, ua, **ctx)
                self.audit.log(AuditLogAction.REFRESH_FAILED, user_id=None, details={"reason": "expired_token"}, ip=ip, user_agent=ua)
                return RefreshFailed(RefreshFailReason.EXPIRED_TOKEN)
            except (jwt.InvalidSignatureError, jwt.DecodeError):
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "refresh", "reason": "invalid_token"})
                self.logger.refresh_invalid_token(ip, ua, **ctx)
                self.audit.log(AuditLogAction.REFRESH_FAILED, user_id=None, details={"reason": "invalid_token"}, ip=ip, user_agent=ua)
                return RefreshFailed(RefreshFailReason.INVALID_TOKEN)

            if payload.get("typ") != "refresh":
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "refresh", "reason": "wrong_type"})
                self.logger.refresh_wrong_type(ip, ua, **ctx)
                self.audit.log(AuditLogAction.REFRESH_FAILED, user_id=None, details={"reason": "wrong_type"}, ip=ip, user_agent=ua)
                return RefreshFailed(RefreshFailReason.WRONG_TOKEN_TYPE)

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
                if token_user_ver != current_user_ver or token_tenant_ver != (tenant.security_version if tenant else 0):
                    increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "refresh", "reason": "security_version_mismatch"})
                    self.logger.refresh_session_expired(user_id, ip, ua, **ctx)
                    self.audit.log(AuditLogAction.REFRESH_FAILED, user_id=user_id, details={"reason": "security_version_mismatch"}, ip=ip, user_agent=ua)
                    return RefreshFailed(RefreshFailReason.SECURITY_VERSION_MISMATCH)

            t0_sess = time.monotonic()
            rec = self.session_repository.get_by_jti(jti)
            record_span("refresh_session_lookup", (time.monotonic() - t0_sess) * 1000)

            if rec is None:
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "refresh", "reason": "unknown_jti"})
                self.logger.refresh_unknown_jti(user_id, ip, ua, **ctx)
                self.audit.log(AuditLogAction.REFRESH_FAILED, user_id=user_id, details={"reason": "unknown_jti"}, ip=ip, user_agent=ua)
                return RefreshFailed(RefreshFailReason.UNKNOWN_SESSION)

            if not rec.valid:
                if permissions_changed_get(tenant.slug if tenant else None, rec.user_id):
                    increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "refresh", "reason": "permissions_changed"})
                    self.audit.log(AuditLogAction.REFRESH_FAILED, user_id=user_id, details={"reason": "permissions_changed"}, ip=ip, user_agent=ua)
                    return RefreshFailed(RefreshFailReason.PERMISSIONS_CHANGED)
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "refresh", "reason": "reuse_detected"})
                self.logger.refresh_reuse_detected(user_id, ip, ua, **ctx)
                self.audit.log(AuditLogAction.REFRESH_FAILED, user_id=user_id, details={"reason": "reuse_detected"}, ip=ip, user_agent=ua)
                self.session_repository.invalidate_all_for_user(rec.user_id, updated_by=rec.user_id)
                return RefreshFailed(RefreshFailReason.SESSION_REUSE_DETECTED)

            if rec.is_expired():
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "refresh", "reason": "session_expired"})
                self.session_repository.update(rec.invalidate(), updated_by=user_id)
                self.logger.refresh_session_expired(user_id, ip, ua, **ctx)
                self.audit.log(AuditLogAction.REFRESH_FAILED, user_id=user_id, details={"reason": "session_expired"}, ip=ip, user_agent=ua)
                return RefreshFailed(RefreshFailReason.SESSION_EXPIRED)

            # -------------------------------
            # 2b️⃣ Device/session binding: teljesen más fingerprint → gyanús, új 2FA kérés
            # -------------------------------
            if self._fingerprint_mismatch(rec, ip, ua):
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "refresh", "reason": "fingerprint_mismatch"})
                self.audit.log(
                    AuditLogAction.REFRESH_SUSPICIOUS_FINGERPRINT,
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
                )
                return RefreshFailed(RefreshFailReason.RE_2FA_REQUIRED)

            # -------------------------------
            # 3️⃣ Token rotation
            # -------------------------------
            self.session_repository.update(rec.invalidate(), updated_by=user_id)

            # -------------------------------
            # 4️⃣ Új refresh token + session (auto_login továbbítás; user_ver/tenant_ver = force revoke)
            # -------------------------------
            auto_login = payload.get("al", False)
            user_ver = current_user_ver
            tenant_ver = tenant.security_version if tenant else 0
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
            self.session_repository.create(new_sess, created_by=user_id)

            # -------------------------------
            # 5️⃣ Új access token (jti a token_allowlisthez; user_ver/tenant_ver = force revoke)
            # -------------------------------
            new_access, access_jti = self.tokens.make_access(user_id, user_ver=user_ver, tenant_ver=tenant_ver, role=getattr(user_for_ver, "role", "user"))

            self.logger.refresh_success(user_id, ip, ua, **ctx)
            increment_metric("platform.auth.success.count", 1.0, tags={"flow": "refresh"})
            self.audit.log(AuditLogAction.REFRESH, user_id=user_id, ip=ip, user_agent=ua)

            # user_for_ver már megvan (version check); visszaadjuk, hogy a route ne hívjon get_by_id-t újra (hot path optimalizáció)
            return RefreshSuccess(
                access_token=new_access,
                refresh_token=new_refresh,
                access_jti=access_jti,
                user=user_for_ver,
                auto_login=bool(auto_login),
            )
