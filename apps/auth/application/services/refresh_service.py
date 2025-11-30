# apps/auth/application/services/refresh_service.py
"""
Frissíti az eléréshez szükséges tokent, ha az lejárt.
Security logolással a hamis vagy visszaélt tokenek észlelésére.
"""
from __future__ import annotations

import jwt
from datetime import datetime, timezone
from apps.auth.ports.repositories import SessionRepositoryPort
from apps.core.security.token_service import TokenService
from apps.auth.domain.session import Session
from apps.core.security.security_logger import SecurityLogger


class RefreshService:
    def __init__(
        self,
        sessions: SessionRepositoryPort,
        tokens: TokenService,
        logger: SecurityLogger
    ):
        self.sessions = sessions
        self.tokens = tokens
        self.logger = logger

    def refresh(self, refresh_token: str, ip: str | None, ua: str | None):

        # -------------------------------
        # 1️⃣ Token dekódolása
        # -------------------------------
        try:
            payload = self.tokens.verify(refresh_token)

        except jwt.ExpiredSignatureError:
            # lejárt refresh token → gyenge támadási forma, de logoljuk
            self.logger.refresh_expired_token(ip, ua)
            return None

        except (jwt.InvalidSignatureError, jwt.DecodeError):
            # manipulált, törött vagy hamis refresh → SECURITY ISSUE
            self.logger.refresh_invalid_token(ip, ua)
            return None

        # verify sikeres → payload megbízható
        if payload.get("typ") != "refresh":
            self.logger.refresh_wrong_type(ip, ua)
            return None

        user_id = int(payload["sub"])
        jti = payload.get("jti")

        # -------------------------------
        # 2️⃣ Session lekérése
        # -------------------------------
        rec = self.sessions.get_by_jti(jti)

        # A) manipulált token: nincs ilyen jti
        if rec is None:
            self.logger.refresh_unknown_jti(user_id, ip, ua)
            return None

        # B) reuse detection: már visszavont refresh token újrahasználata
        if not rec.valid:
            # VISSZAÉLÉS, TOKEN THEFT GYANÚ!!
            self.logger.refresh_reuse_detected(user_id, ip, ua)

            # minden session érvénytelenítése
            self.sessions.invalidate_all_for_user(rec.user_id)
            return None

        # C) refresh session lejárt
        if rec.is_expired():
            self.sessions.update(rec.invalidate())
            self.logger.refresh_session_expired(user_id, ip, ua)
            return None

        # -------------------------------
        # 3️⃣ Token rotation
        # -------------------------------
        self.sessions.update(rec.invalidate())

        # -------------------------------
        # 4️⃣ Új refresh token + session
        # -------------------------------
        new_refresh, new_claims = self.tokens.make_refresh_pair(user_id)
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
        self.sessions.create(new_sess)

        # -------------------------------
        # 5️⃣ Új access token
        # -------------------------------
        new_access = self.tokens.make_access(user_id)

        self.logger.refresh_success(user_id, ip, ua)

        return new_access, new_refresh
