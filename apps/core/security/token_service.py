# apps/core/security/token_service.py 
# JWT token kezelés
# Mit csinál: Access és refresh JWT tokenek előállítása (HS256), ellenőrzése,
# valamint token hash-elése (pl. session tároláshoz). A titkot és TTL-eket
# a konstruktor kapja (általában config/settings-ből).
# Ki használja: AppContainer hozza létre; AuthMiddleware és auth service-ek
# (login, refresh, logout) a di.py get_token_service() útján érik el.
# 2026.02.14 - Sárközi Mihály

from __future__ import annotations

import hashlib
import datetime
import uuid
import jwt
from typing import Any, Dict


class TokenService:
    """
    JWT (access + refresh) tokenek létrehozása és ellenőrzése HS256 aláírással.
    A secret és lejárati idők konstruktorban adandók (pl. config).
    """

    def __init__(
        self,
        secret: str,
        issuer: str | None = None,
        access_exp_min: int = 15,
        refresh_exp_min: int = 60 * 24 * 30,
    ):
        """
        secret: JWT aláíráshoz használt titok (élesben erős, .env-ből).
        issuer: Opcionális "iss" claim (pl. "AIPLAZA").
        access_exp_min: Access token érvényessége percekben.
        refresh_exp_min: Refresh token érvényessége percekben (pl. 30 nap).
        """
        self.secret = secret
        self.issuer = issuer
        self.access_exp = access_exp_min
        self.refresh_exp = refresh_exp_min
        self.alg = "HS256"

    def _now(self) -> datetime.datetime:
        """UTC aktuális idő – exp/iat claim-ekhez."""
        return datetime.datetime.utcnow()

    def hash_token(self, token: str) -> str:
        """SHA256 hash a nyers tokenből (pl. session táblában tároláshoz)."""
        return hashlib.sha256(token.encode()).hexdigest()

    def make_access(self, user_id: int) -> tuple[str, str]:
        """
        Access JWT előállítása. Payload: sub=user_id, typ="access", jti, iss, exp, iat.
        Vissza: (token_str, jti) – a jti a token_allowlist regisztrálásához kell (törlés/logout után 401).
        """
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "typ": "access",
            "jti": jti,
            "iss": self.issuer,
            "exp": self._now() + datetime.timedelta(minutes=self.access_exp),
            "iat": self._now(),
        }
        token = jwt.encode(payload, self.secret, algorithm=self.alg)
        return token, jti

    def make_refresh_pair(self, user_id: int, auto_login: bool = False) -> tuple[str, Dict[str, Any]]:
        """
        Refresh JWT + payload. Payload: sub, typ="refresh", jti, exp, iat, al (auto_login).
        al=True: cookie max_age 30 nap (aktivitásnál kitolódik), al=False: session cookie.
        """
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "typ": "refresh",
            "jti": jti,
            "exp": self._now() + datetime.timedelta(minutes=self.refresh_exp),
            "iat": self._now(),
            "al": auto_login,
        }
        token = jwt.encode(payload, self.secret, algorithm=self.alg)
        return token, payload

    def verify(self, token: str) -> Dict[str, Any]:
        """
        JWT ellenőrzése (aláírás + lejárat). Hibás/lejárt token esetén
        jwt.InvalidTokenError (vagy alosztály) dobódik.
        """
        return jwt.decode(token, self.secret, algorithms=[self.alg])

    def decode_ignore_exp(self, token: str) -> Dict[str, Any] | None:
        """
        JWT payload lekérése aláírás ellenőrzéssel, de lejárat figyelmen kívül hagyásával.
        Logout-nál: lejárt refresh tokenből is kiolvasható a user_id (sub).
        Hibás token esetén None.
        """
        try:
            return jwt.decode(
                token,
                self.secret,
                algorithms=[self.alg],
                options={"verify_exp": False},
            )
        except (jwt.InvalidSignatureError, jwt.DecodeError):
            return None
