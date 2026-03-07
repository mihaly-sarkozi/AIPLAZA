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
        audience: str | None = None,
        access_exp_min: int = 15,
        refresh_exp_min: int = 60 * 24 * 30,
    ):
        """
        secret: JWT aláíráshoz használt titok (élesben erős, .env-ből).
        issuer: "iss" claim (élesben kötelező – más környezetből kiadott token ne legyen elfogadható).
        audience: Opcionális "aud" claim (pl. API azonosító).
        access_exp_min: Access token érvényessége percekben.
        refresh_exp_min: Refresh token érvényessége percekben (pl. 30 nap).
        """
        self.secret = secret
        self.issuer = issuer
        self.audience = audience
        self.access_exp = access_exp_min
        self.refresh_exp = refresh_exp_min
        self.alg = "HS256"

    def _now(self) -> datetime.datetime:
        """UTC aktuális idő – exp/iat claim-ekhez (timezone-aware)."""
        return datetime.datetime.now(datetime.timezone.utc)

    def hash_token(self, token: str) -> str:
        """SHA256 hash a nyers tokenből (pl. session táblában tároláshoz)."""
        return hashlib.sha256(token.encode()).hexdigest()

    def make_access(
        self,
        user_id: int,
        user_ver: int = 0,
        tenant_ver: int = 0,
        role: str = "user",
    ) -> tuple[str, str]:
        """
        Access JWT előállítása. Payload: sub, typ="access", jti, user_ver, tenant_ver, role, iss, aud?, nbf, exp, iat.
        user_ver/tenant_ver: security version – ha a middleware-ben nem egyezik a jelenlegivel, a token bukik (force revoke).
        role: token-driven auth-hoz (light path: DB user load nélkül elég a token claim).
        """
        now = self._now()
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "typ": "access",
            "jti": jti,
            "user_ver": user_ver,
            "tenant_ver": tenant_ver,
            "role": role,
            "exp": now + datetime.timedelta(minutes=self.access_exp),
            "iat": now,
            "nbf": now,
        }
        if self.issuer is not None:
            payload["iss"] = self.issuer
        if self.audience is not None:
            payload["aud"] = self.audience
        token = jwt.encode(payload, self.secret, algorithm=self.alg)
        return token, jti

    def make_refresh_pair(
        self,
        user_id: int,
        auto_login: bool = False,
        user_ver: int = 0,
        tenant_ver: int = 0,
    ) -> tuple[str, Dict[str, Any]]:
        """
        Refresh JWT + payload. Payload: sub, typ="refresh", jti, user_ver, tenant_ver, iss, aud?, nbf, exp, iat, al.
        user_ver/tenant_ver: security version – refresh ellenőrzéskor hasonlítjuk; nem egyezik → token bukik.
        """
        now = self._now()
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "typ": "refresh",
            "jti": jti,
            "user_ver": user_ver,
            "tenant_ver": tenant_ver,
            "exp": now + datetime.timedelta(minutes=self.refresh_exp),
            "iat": now,
            "nbf": now,
            "al": auto_login,
        }
        if self.issuer is not None:
            payload["iss"] = self.issuer
        if self.audience is not None:
            payload["aud"] = self.audience
        token = jwt.encode(payload, self.secret, algorithm=self.alg)
        return token, payload

    def verify(self, token: str) -> Dict[str, Any]:
        """
        JWT ellenőrzése: aláírás, lejárat (exp), iss, opcionális aud, nbf.
        Más környezetből vagy más célra kiadott token (rossz iss/aud) nem fogadható el.
        Hibás/lejárt/rossz iss/aud token esetén jwt.InvalidTokenError dobódik.
        """
        kwargs: Dict[str, Any] = {"algorithms": [self.alg]}
        if self.issuer is not None:
            kwargs["issuer"] = self.issuer
        if self.audience is not None:
            kwargs["audience"] = self.audience
        return jwt.decode(token, self.secret, **kwargs)

    def decode_ignore_exp(self, token: str) -> Dict[str, Any] | None:
        """
        JWT payload lekérése aláírással, iss/aud ellenőrzéssel, de lejárat figyelmen kívül.
        Logout-nál: lejárt refresh tokenből is kiolvasható a user_id (sub).
        Rossz iss/aud token nem fogadható el. Hibás token esetén None.
        """
        try:
            kwargs: Dict[str, Any] = {
                "algorithms": [self.alg],
                "options": {"verify_exp": False},
            }
            if self.issuer is not None:
                kwargs["issuer"] = self.issuer
            if self.audience is not None:
                kwargs["audience"] = self.audience
            return jwt.decode(token, self.secret, **kwargs)
        except (jwt.InvalidSignatureError, jwt.DecodeError, jwt.InvalidIssuerError, jwt.InvalidAudienceError):
            return None
