# features/auth/application/services/refresh_service.py
from __future__ import annotations

from datetime import datetime, timezone
from features.auth.ports.repositories import SessionRepositoryPort
from infrastructure.security.tokens import TokenService
from features.auth.domain.session import Session


class RefreshService:
    def __init__(self, sessions: SessionRepositoryPort, tokens: TokenService):
        self.sessions = sessions
        self.tokens = tokens

    def refresh(self, refresh_token: str, ip: str | None, ua: str | None):
        # 1️⃣ token dekódolása
        try:
            payload = self.tokens.verify(refresh_token)
            if payload.get("typ") != "refresh":
                return None
        except Exception:
            return None

        # 2️⃣ meglévő session ellenőrzése
        rec = self.sessions.get_by_jti(payload["jti"])
        if not rec or not rec.valid:
            return None

        # ⚠️ 3️⃣ reuse detection: ha valaki visszavont refresh tokent használna
        if not rec.valid:
            # → azonnal minden session-t visszavonunk ennél a felhasználónál
            self.sessions.invalidate_all_for_user(rec.user_id)
            return None

        if rec.is_expired():
            # ha lejárt, érvénytelenítjük
            self.sessions.update(rec.invalidate())
            return None

        # 3️⃣ régi token azonnali inaktiválása (rotation)
        self.sessions.update(rec.invalidate())

        # 4️⃣ új refresh token generálása (új jti)
        new_refresh, new_claims = self.tokens.make_refresh_pair(int(payload["sub"]))
        new_hash = self.tokens.hash_token(new_refresh)

        exp_val = new_claims["exp"]
        exp_dt = exp_val if isinstance(exp_val, datetime) else datetime.fromtimestamp(exp_val, tz=timezone.utc)

        # 5️⃣ új session létrehozása
        new_sess = Session.new(
            user_id=int(payload["sub"]),
            jti=new_claims["jti"],
            token_hash=new_hash,
            expires_at=exp_dt,
            ip=ip,
            user_agent=ua,
        )
        self.sessions.create(new_sess)

        # 6️⃣ új access token
        new_access = self.tokens.make_access(int(payload["sub"]))

        return new_access, new_refresh
