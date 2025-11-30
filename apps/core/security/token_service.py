# infrastructure/security/token_service.py
from __future__ import annotations

import jwt, hashlib, datetime, uuid
from typing import Any, Dict


class TokenService:
    def __init__(self, secret: str, issuer: str | None = None, access_exp_min: int = 15, refresh_exp_min: int = 60 * 24 * 30):
        self.secret = secret
        self.issuer = issuer
        self.access_exp = access_exp_min
        self.refresh_exp = refresh_exp_min
        self.alg = "HS256"

    def _now(self):
        return datetime.datetime.utcnow()

    def hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def make_access(self, user_id: int) -> str:
        payload = {
            "sub": str(user_id),
            "typ": "access",
            "iss": self.issuer,
            "exp": self._now() + datetime.timedelta(minutes=self.access_exp),
            "iat": self._now()
        }
        return jwt.encode(payload, self.secret, algorithm=self.alg)

    def make_refresh_pair(self, user_id: int) -> tuple[str, Dict[str, Any]]:
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "typ": "refresh",
            "jti": jti,
            "exp": self._now() + datetime.timedelta(minutes=self.refresh_exp),
            "iat": self._now()
        }
        token = jwt.encode(payload, self.secret, algorithm=self.alg)
        return token, payload

    def verify(self, token: str) -> Dict[str, Any]:
        return jwt.decode(token, self.secret, algorithms=[self.alg])
