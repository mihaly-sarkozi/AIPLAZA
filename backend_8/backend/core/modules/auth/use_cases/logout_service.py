# backend/core/modules/auth/use_cases/logout_service.py
# Feladat: Refresh token alapú logout application service. A kliens felé idempotens, csendes kiléptetést ad, miközben valid token esetén sessiont érvénytelenít, lejárt/hibás/replay token esetén pedig security logot és audit bejegyzést ír. Auth use case réteg a logout flowhoz.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import jwt
from core.modules.auth.domain.dto import TenantAuthContext
from core.modules.auth.repository.persistence import SessionRepository
from core.infrastructure.audit.const.audit_log_action_const import AuditLogAction
from core.modules.auth.service.token_service import TokenService
from core.kernel.logging.security_logger import SecurityLogger
from core.infrastructure.audit.service.audit_service import AuditService
from core.kernel.db.transactional_service import TransactionalServiceMixin
from core.kernel.logging.observability import increment_metric


# Ez a függvény a(z) ctx logikáját valósítja meg.
def _ctx(tenant: TenantAuthContext | None) -> dict:
    return {
        "tenant_slug": tenant.slug if tenant else None,
        "correlation_id": tenant.correlation_id if tenant else None,
    }

# Kilépés üzleti logikája
class LogoutService(TransactionalServiceMixin):
    # Ez a metódus a Python-specifikus speciális működést valósítja meg.
    def __init__(
        self,
        session_repository: SessionRepository,
        tokens: TokenService,
        logger: SecurityLogger,
        audit_service: AuditService,
        transaction_manager=None,
    ):
        super().__init__(transaction_manager=transaction_manager)
        self.session_repository = session_repository
        self.tokens = tokens
        self.logger = logger
        self.audit = audit_service

    # Kilépés
    def logout(
        self,
        refresh_token: str,
        ip: str | None = None,
        ua: str | None = None,
        *,
        tenant: TenantAuthContext | None = None,
    ) -> bool:
        """Mindig sikeres kiléptetés a kliens szempontjából. Hibát (lejárt/érvénytelen token) csak log/auditba írjuk."""
        with self._transaction():
            ctx = _ctx(tenant)
            # -------------------------------
            # 1. Érvényes token → session érvénytelenítés, success log
            # -------------------------------
            try:
                payload = self.tokens.verify(refresh_token)
            except jwt.ExpiredSignatureError:
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "logout", "reason": "expired_token"})
                return self._logout_with_expired_token(refresh_token, ip, ua, tenant=tenant)
            except (jwt.InvalidSignatureError, jwt.DecodeError):
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "logout", "reason": "invalid_token"})
                self.logger.logout_invalid_token(ip, ua, **ctx)
                self.audit.log(AuditLogAction.LOGOUT_FAILED, user_id=None, details={"reason": "invalid_token"}, ip=ip, user_agent=ua)
                return True

            if payload.get("typ") != "refresh":
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "logout", "reason": "wrong_type"})
                self.logger.logout_wrong_type(ip, ua, **ctx)
                self.audit.log(AuditLogAction.LOGOUT_FAILED, user_id=None, details={"reason": "wrong_type"}, ip=ip, user_agent=ua)
                return True

            jti = payload.get("jti")
            user_id = int(payload["sub"])
            session = self.session_repository.get_by_jti(jti)
            if not session:
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "logout", "reason": "unknown_jti"})
                self.logger.logout_unknown_jti(user_id, ip, ua, **ctx)
                self.audit.log(AuditLogAction.LOGOUT_FAILED, user_id=user_id, details={"reason": "unknown_jti"}, ip=ip, user_agent=ua)
                return True

            hashed = self.tokens.hash_token(refresh_token)
            if session.token_hash != hashed:
                increment_metric("platform.auth.failure.count", 1.0, tags={"flow": "logout", "reason": "replay_detected"})
                self.logger.logout_replay_detected(user_id, ip, ua, **ctx)
                self.audit.log(AuditLogAction.LOGOUT_FAILED, user_id=user_id, details={"reason": "replay_detected"}, ip=ip, user_agent=ua)
                return True

            updated = session.invalidate()
            self.session_repository.update(updated, updated_by=user_id)
            self.logger.logout_success(user_id, ip, ua, **ctx)
            increment_metric("platform.auth.success.count", 1.0, tags={"flow": "logout"})
            self.audit.log(AuditLogAction.LOGOUT, user_id=user_id, ip=ip, user_agent=ua)
            return True

    # Kilépés lejárt token esetén
    def _logout_with_expired_token(
        self,
        refresh_token: str,
        ip: str | None,
        ua: str | None,
        *,
        tenant: TenantAuthContext | None = None,
    ) -> bool:
        """Lejárt refresh token: először session érvénytelenítés (ha megvan jti), utána a hiba bejegyzése."""
        ctx = _ctx(tenant)
        payload = self.tokens.decode_ignore_exp(refresh_token)
        if payload and payload.get("typ") == "refresh" and payload.get("jti") and payload.get("sub"):
            jti = payload["jti"]
            user_id = int(payload["sub"])
            session = self.session_repository.get_by_jti(jti)
            if session:
                hashed = self.tokens.hash_token(refresh_token)
                if session.token_hash == hashed:
                    updated = session.invalidate()
                    self.session_repository.update(updated, updated_by=user_id)
        user_id_audit = None
        if payload and payload.get("sub") is not None:
            try:
                user_id_audit = int(payload["sub"])
            except (TypeError, ValueError):
                pass
        self.logger.logout_expired_token(ip, ua, **ctx)
        self.audit.log(
            AuditLogAction.LOGOUT_FAILED,
            user_id=user_id_audit,
            details={"reason": "expired_token"},
            ip=ip,
            user_agent=ua,
        )
        return True
