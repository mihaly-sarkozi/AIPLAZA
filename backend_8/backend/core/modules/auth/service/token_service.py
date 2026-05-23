# backend/core/modules/auth/service/token_service.py
# Feladat: JWT access, refresh, platform-admin és demo-login tokenek kiadását és ellenőrzését végzi. HS256 aláírást, issuer/audience claimet, security version claimet, token hash-elést és clock dependencyt használ, hogy a session tárolás és token validáció egységes legyen. Auth service réteg, amelyet middleware, use case-ek és router helperök használnak.
# Sárközi Mihály - 2026.05.21

from __future__ import annotations

import hashlib
import datetime
import uuid
import jwt
from typing import Any, Dict

from core.kernel.runtime.clock import Clock, SystemClock


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
        clock: Clock | None = None,
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
        self.clock = clock or SystemClock()

    def _now(self) -> datetime.datetime:
        """UTC aktuális idő – exp/iat claim-ekhez (timezone-aware)."""
        return self.clock.now()

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

    def make_platform_admin_access(
        self,
        user_id: int,
        user_ver: int = 0,
        role: str = "admin",
    ) -> tuple[str, str]:
        """Access token for the public-schema platform admin console."""
        now = self._now()
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "typ": "platform_admin_access",
            "jti": jti,
            "user_ver": user_ver,
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

    def make_platform_admin_refresh_pair(
        self,
        user_id: int,
        user_ver: int = 0,
    ) -> tuple[str, Dict[str, Any]]:
        """Refresh JWT for the public-schema platform admin console."""
        now = self._now()
        jti = str(uuid.uuid4())
        payload = {
            "sub": str(user_id),
            "typ": "platform_admin_refresh",
            "jti": jti,
            "user_ver": user_ver,
            "exp": now + datetime.timedelta(minutes=self.refresh_exp),
            "iat": now,
            "nbf": now,
        }
        if self.issuer is not None:
            payload["iss"] = self.issuer
        if self.audience is not None:
            payload["aud"] = self.audience
        token = jwt.encode(payload, self.secret, algorithm=self.alg)
        return token, payload

    def make_demo_login(
        self,
        *,
        user_id: int,
        tenant_slug: str,
        email: str,
        name: str | None,
        demo_expires_at: datetime.datetime,
    ) -> str:
        now = self._now()
        payload = {
            "sub": str(user_id),
            "typ": "demo_login",
            "tenant": tenant_slug,
            "email": email,
            "name": name,
            "demo_expires_at": demo_expires_at.isoformat(),
            "exp": demo_expires_at,
            "iat": now,
            "nbf": now,
        }
        if self.issuer is not None:
            payload["iss"] = self.issuer
        if self.audience is not None:
            payload["aud"] = self.audience
        return jwt.encode(payload, self.secret, algorithm=self.alg)

    def verify(self, token: str) -> Dict[str, Any]:
        """
        JWT ellenőrzése: aláírás, exp, iss, aud (ha megadva), nbf (ha a tokenben van).
        Policy: mindig iss + aud (ha configban van) + nbf ellenőrzés – más környezet/cél token elutasítva.
        Hibás/lejárt/rossz iss/aud/nbf → jwt.InvalidTokenError.
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
