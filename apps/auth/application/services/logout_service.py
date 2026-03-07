# apps/auth/application/services/logout_service.py
# Kilépteti a usert, törli a tokeneket. Csendes kiléptetés: ha van user (pl. lejárt tokenból),
# először érvénytelenítjük a sessiont (kilépés „sikerül”), aztán a hibát csak a log/auditba jegyezzük.
# 2026.03.07 - Sárközi Mihály

from __future__ import annotations

import jwt
from apps.auth.ports import SessionRepositoryInterface
from apps.core.security.token_service import TokenService
from apps.core.security.security_logger import SecurityLogger
from apps.audit.application.audit_service import AuditService


class LogoutService:
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

    def logout(self, refresh_token: str, ip: str | None = None, ua: str | None = None) -> bool:
        """Mindig sikeres kiléptetés a kliens szempontjából. Hibát (lejárt/érvénytelen token) csak log/auditba írjuk."""

        # -------------------------------
        # 1. Érvényes token → session érvénytelenítés, success log
        # -------------------------------
        try:
            payload = self.tokens.verify(refresh_token)
        except jwt.ExpiredSignatureError:
            # Lejárt token: először kiléptetünk (decode_ignore_exp → session invalidate), utána bejegyezzük a hibát
            return self._logout_with_expired_token(refresh_token, ip, ua)
        except (jwt.InvalidSignatureError, jwt.DecodeError):
            self.logger.logout_invalid_token(ip, ua)
            self.audit.log("logout_failed", user_id=None, details={"reason": "invalid_token"}, ip=ip, user_agent=ua)
            return True

        if payload.get("typ") != "refresh":
            self.logger.logout_wrong_type(ip, ua)
            self.audit.log("logout_failed", user_id=None, details={"reason": "wrong_type"}, ip=ip, user_agent=ua)
            return True

        jti = payload.get("jti")
        user_id = int(payload["sub"])
        session = self.session_repository.get_by_jti(jti)
        if not session:
            self.logger.logout_unknown_jti(user_id, ip, ua)
            self.audit.log("logout_failed", user_id=user_id, details={"reason": "unknown_jti"}, ip=ip, user_agent=ua)
            return True

        hashed = self.tokens.hash_token(refresh_token)
        if session.token_hash != hashed:
            self.logger.logout_replay_detected(user_id, ip, ua)
            self.audit.log("logout_failed", user_id=user_id, details={"reason": "replay_detected"}, ip=ip, user_agent=ua)
            return True

        updated = session.invalidate()
        self.session_repository.update(updated)
        self.logger.logout_success(user_id, ip, ua)
        self.audit.log("logout", user_id=user_id, ip=ip, user_agent=ua)
        return True

    def _logout_with_expired_token(self, refresh_token: str, ip: str | None, ua: str | None) -> bool:
        """Lejárt refresh token: először session érvénytelenítés (ha megvan jti), utána a hiba bejegyzése."""
        payload = self.tokens.decode_ignore_exp(refresh_token)
        if payload and payload.get("typ") == "refresh" and payload.get("jti") and payload.get("sub"):
            jti = payload["jti"]
            user_id = int(payload["sub"])
            session = self.session_repository.get_by_jti(jti)
            if session:
                hashed = self.tokens.hash_token(refresh_token)
                if session.token_hash == hashed:
                    updated = session.invalidate()
                    self.session_repository.update(updated)
        user_id_audit = None
        if payload and payload.get("sub") is not None:
            try:
                user_id_audit = int(payload["sub"])
            except (TypeError, ValueError):
                pass
        self.logger.logout_expired_token(ip, ua)
        self.audit.log(
            "logout_failed",
            user_id=user_id_audit,
            details={"reason": "expired_token"},
            ip=ip,
            user_agent=ua,
        )
        return True
