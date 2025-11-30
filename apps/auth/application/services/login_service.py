# apps/auth/application/services/login_service.py
"""
Belépteti a usert és logolja a sikerességét is.
Sikeres belépés eredénye egy access token és egy refresh token.
"""

from __future__ import annotations
from passlib.hash import bcrypt_sha256 as pwd_hasher
from datetime import datetime, timezone
from apps.auth.ports.repositories import UserRepositoryPort, SessionRepositoryPort
from apps.core.security.token_service import TokenService
from apps.auth.domain.session import Session
from apps.core.security.security_logger import SecurityLogger


class LoginService:
    def __init__(
        self,
        users: UserRepositoryPort,
        sessions: SessionRepositoryPort,
        tokens: TokenService,
        logger: SecurityLogger
    ):
        self.users = users
        self.sessions = sessions
        self.tokens = tokens
        self.logger = logger

    def login(self, email: str, password: str, ip: str | None, ua: str | None):

        user = self.users.get_by_email(email)

        # --- A) user nem létezik ---
        if user is None:
            self.logger.login_invalid_user_attempt(email, ip, ua)
            return None, None

        # --- B) user létezik, de inaktív ---
        if not user.is_active:
            self.logger.login_inactive_user_attempt(user.id, ip, ua)
            return None, None

        # --- C) hibás jelszó ---
        if not pwd_hasher.verify(password, user.password_hash):
            self.logger.login_bad_password_attempt(user.id, ip, ua)
            return None, None

        # --- D) minden valid → sikeres login ---
        self.logger.login_successful_login(user.id, ip, ua)

        # Single-session policy
        self.sessions.invalidate_all_for_user(user.id)

        # refresh + claims
        refresh, claims = self.tokens.make_refresh_pair(user.id)

        exp_val = claims["exp"]
        exp_dt = exp_val if isinstance(exp_val, datetime) else \
            datetime.fromtimestamp(exp_val, tz=timezone.utc)

        hashed_refresh = self.tokens.hash_token(refresh)

        s = Session.new(
            user_id=user.id,
            jti=claims["jti"],
            token_hash=hashed_refresh,
            expires_at=exp_dt,
            ip=ip,
            user_agent=ua,
        )
        self.sessions.create(s)

        access = self.tokens.make_access(user.id)
        return access, refresh
