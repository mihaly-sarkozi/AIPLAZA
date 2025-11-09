# features/auth/application/services/login_service.py
from __future__ import annotations
import hashlib
from passlib.hash import bcrypt_sha256 as pwd_hasher
from datetime import datetime, timezone
from features.auth.ports.repositories import UserRepositoryPort, SessionRepositoryPort
from features.auth.domain.session import Session
from infrastructure.security.tokens import TokenService

class LoginService:
    def __init__(self, users: UserRepositoryPort, sessions: SessionRepositoryPort, tokens: TokenService):
        self.users = users
        self.sessions = sessions
        self.tokens = tokens

    def login(self, email: str, password: str, ip: str | None, ua: str | None):
        user = self.users.get_by_email(email)
        if not user or not user.is_active or not pwd_hasher.verify(password, user.password_hash):
            return None, None

        # single-session: érvénytelenítsd a régieket
        self.sessions.invalidate_all_for_user(user.id)

        # refresh + claims
        refresh, claims = self.tokens.make_refresh_pair(user.id)

        exp_val = claims["exp"]
        exp_dt = exp_val if isinstance(exp_val, datetime) else datetime.fromtimestamp(exp_val, tz=timezone.utc)

        # SHA-256 hash tárolása
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

        # access token
        access = self.tokens.make_access(user.id)
        return access, refresh
