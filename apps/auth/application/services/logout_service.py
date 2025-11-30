# apps/auth/application/services/logout_service.py
"""
Kilépteti a usert, törli a tokeneket,
Figyel ha valaki hamisitott vagy hibás tokenekkel próbálkozik
"""
from __future__ import annotations

import jwt
from apps.auth.ports.repositories import SessionRepositoryPort
from apps.core.security.token_service import TokenService
from apps.core.security.security_logger import SecurityLogger

class LogoutService:
    def __init__(self, sessions: SessionRepositoryPort, tokens: TokenService, logger: SecurityLogger):
        self.sessions = sessions
        self.tokens = tokens
        self.logger = logger

    def logout(self, refresh_token: str, ip: str | None = None, ua: str | None = None):

        # -------------------------------
        # 1. Token dekódolás
        # -------------------------------
        try:
            payload = self.tokens.verify(refresh_token)

        except jwt.ExpiredSignatureError:
            # lejárt refresh → nem veszélyes, csak érvénytelen
            self.logger.logout_expired_token(ip, ua)
            return False


        except (jwt.InvalidSignatureError, jwt.DecodeError):
            # manipulált vagy törött token → SECURITY ALERT
            self.logger.logout_invalid_token(ip, ua)
            return False

        # ellenőrzés után payload megbízható
        if payload.get("typ") != "refresh":
            self.logger.logout_wrong_type(ip, ua)
            return False

        jti = payload.get("jti")
        user_id = int(payload["sub"])

        # -------------------------------
        # 2. Session keresése
        # -------------------------------
        session = self.sessions.get_by_jti(jti)
        if not session:
            self.logger.logout_unknown_jti(user_id, ip, ua)
            return False

        # -------------------------------
        # 3. Token-hash egyezés ellenőrzése
        # -------------------------------
        hashed = self.tokens.hash_token(refresh_token)
        if session.token_hash != hashed:
            # token theft / replay attack gyanú!
            self.logger.logout_replay_detected(user_id, ip, ua)
            return False

        # -------------------------------
        # 4. Token érvénytelenítése
        # -------------------------------
        updated = session.invalidate()
        self.sessions.update(updated)

        self.logger.logout_success(user_id, ip, ua)
        return True
